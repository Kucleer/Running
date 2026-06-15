from datetime import date, timedelta
from backend.garmin_client import GarminClient
from backend.database import get_db
from backend.splits import (
    is_running_activity_type,
    is_meaningful_split,
    normalize_official_splits,
    save_splits,
    splits_from_detail_json,
)


class SyncService:
    def __init__(self, tokenstore=None):
        self.garmin = None
        self._progress = {'status': 'idle', 'current': 0, 'total': 0}
        self._tokenstore = tokenstore

    def sync(self, email, password, sync_health=True, health_days=14):
        self.garmin = GarminClient(tokenstore=self._tokenstore)
        login_result = self.garmin.login(email, password)

        if not login_result['success']:
            return {
                'error': login_result.get('error', '登录失败'),
                'need_captcha': login_result.get('need_captcha', False)
            }

        db = get_db()
        
        # Phase 1: Fetch activity list and insert basic data
        activities = self.garmin.fetch_activities(start=0, limit=500)
        
        new_activities = []
        for activity in activities:
            existing = db.execute(
                "SELECT id FROM activities WHERE id=?",
                (activity['id'],)
            ).fetchone()

            if not existing:
                db.execute("""
                    INSERT OR IGNORE INTO activities
                    (id, name, type, start_time, duration, distance,
                     avg_heart_rate, max_heart_rate, avg_pace, elevation_gain, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    activity['id'], activity['name'], activity['type'],
                    activity['start_time'], activity['duration'], activity['distance'],
                    activity['avg_heart_rate'], activity['max_heart_rate'],
                    activity['avg_pace'], activity['elevation_gain'], activity['raw_json']
                ))
                new_activities.append(activity)

        db.commit()
        
        # Phase 2: Fetch details only for new activities
        detail_count = 0
        for activity in new_activities:
            # Fetch detailed activity data (running dynamics, etc.)
            detail = self.garmin.fetch_activity_details(activity['id'])
            if detail:
                cols = []
                vals = []
                for k in ['avg_cadence', 'max_cadence', 'avg_ground_contact_time',
                           'avg_vertical_oscillation', 'avg_stride_length',
                           'training_effect', 'vo2max', 'lactate_threshold', 'detail_json']:
                    v = detail.get(k)
                    if v is not None:
                        cols.append(f"{k}=?")
                        vals.append(v)
                if cols:
                    vals.append(activity['id'])
                    db.execute(f"UPDATE activities SET {','.join(cols)} WHERE id=?", vals)

            if is_running_activity_type(activity['type']):
                splits = []
                try:
                    splits = normalize_official_splits(
                        self.garmin.fetch_activity_splits(activity['id']),
                        source='garmin'
                    )
                except Exception:
                    splits = []
                useful_splits = [s for s in splits if is_meaningful_split(s)]
                if not useful_splits and detail and detail.get('detail_json'):
                    useful_splits = splits_from_detail_json(detail.get('detail_json'))
                if useful_splits:
                    save_splits(db, activity['id'], useful_splits)

            # Fetch weather data for the activity
            weather = self.garmin.fetch_activity_weather(activity['id'])
            if weather:
                w_cols = []
                w_vals = []
                for k in ['temperature', 'humidity', 'wind_speed', 'weather_condition', 'weather_json']:
                    v = weather.get(k)
                    if v is not None:
                        w_cols.append(f"{k}=?")
                        w_vals.append(v)
                if w_cols:
                    w_vals.append(activity['id'])
                    db.execute(f"UPDATE activities SET {','.join(w_cols)} WHERE id=?", w_vals)
            
            detail_count += 1

        db.commit()
        db.close()

        # Sync health data if requested
        health_fetched = 0
        if sync_health:
            health_fetched = self.sync_health_data(health_days)

        return {
            'total_checked': len(activities),
            'new_count': len(new_activities),
            'detail_count': detail_count,
            'health_fetched': health_fetched
        }

    def sync_health_data(self, days=14):
        """Sync health data for recent days."""
        if not self.garmin:
            self.garmin = GarminClient(tokenstore=self._tokenstore)
            login_result = self.garmin.login('', '')
            if not login_result.get('success'):
                return 0

        fetched = 0
        for i in range(days):
            d = (date.today() - timedelta(days=i)).isoformat()
            try:
                hd = self.garmin.fetch_health_data(d)
                if hd:
                    db = get_db()
                    existing = db.execute("SELECT date FROM health_data WHERE date=?", (d,)).fetchone()
                    if existing:
                        cols = []
                        vals = []
                        for k in ['hrv_status', 'hrv_avg', 'sleep_score', 'sleep_duration',
                                   'resting_hr', 'body_battery_max', 'body_battery_min',
                                   'avg_stress', 'training_status', 'vo2max', 'raw_json']:
                            v = hd.get(k)
                            if v is not None:
                                cols.append(f"{k}=?")
                                vals.append(v)
                        if cols:
                            vals.append(d)
                            db.execute(f"UPDATE health_data SET {','.join(cols)} WHERE date=?", vals)
                    else:
                        db.execute("""
                            INSERT INTO health_data (date, hrv_status, hrv_avg, sleep_score, sleep_duration,
                                resting_hr, body_battery_max, body_battery_min, avg_stress,
                                training_status, vo2max, raw_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (d, hd.get('hrv_status'), hd.get('hrv_avg'), hd.get('sleep_score'),
                              hd.get('sleep_duration'), hd.get('resting_hr'),
                              hd.get('body_battery_max'), hd.get('body_battery_min'),
                              hd.get('avg_stress'), hd.get('training_status'),
                              hd.get('vo2max'), hd.get('raw_json')))
                    db.commit()
                    db.close()
                    fetched += 1
            except Exception:
                pass

        return fetched

    def get_progress(self):
        return self._progress
