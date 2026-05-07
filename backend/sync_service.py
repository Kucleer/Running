from backend.garmin_client import GarminClient
from backend.database import get_db


class SyncService:
    def __init__(self, tokenstore=None):
        self.garmin = None
        self._progress = {'status': 'idle', 'current': 0, 'total': 0}
        self._tokenstore = tokenstore

    def sync(self, email, password):
        self.garmin = GarminClient(tokenstore=self._tokenstore)
        login_result = self.garmin.login(email, password)

        if not login_result['success']:
            return {
                'error': login_result.get('error', '登录失败'),
                'need_captcha': login_result.get('need_captcha', False)
            }

        db = get_db()
        activities = self.garmin.fetch_activities(start=0, limit=500)

        new_count = 0
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
                new_count += 1

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

        db.commit()
        db.close()

        return {
            'new_count': new_count,
            'total_checked': len(activities)
        }

    def get_progress(self):
        return self._progress
