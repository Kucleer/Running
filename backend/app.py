import os
import json
from flask import Flask, send_from_directory, jsonify, request, Response
from backend.database import init_db, get_db
from backend.sync_service import SyncService
from backend.chat_service import ChatService
from backend.llm_client import LLMClient
from backend.config import get_config
from backend.splits import (
    build_split_summary,
    get_activity_splits,
    is_meaningful_split,
    is_running_activity_type,
    normalize_official_splits,
    RUNNING_ACTIVITY_TYPES,
    save_splits,
    splits_from_detail_json,
)


sync_service = None
chat_service = ChatService()


def _init_sync_service():
    global sync_service
    from backend.database import _get_db_path
    tokenstore = os.path.join(os.path.dirname(_get_db_path()), 'garmin_tokens')
    sync_service = SyncService(tokenstore=tokenstore)


def _get_training_summary(include_strength=False):
    db = get_db()
    
    # Get current month stats
    current_month = db.execute("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(distance), 0) as total_distance,
            COALESCE(AVG(avg_pace), 0) as avg_pace,
            COALESCE(AVG(avg_heart_rate), 0) as avg_hr
        FROM activities
        WHERE type='running'
          AND strftime('%Y-%m', start_time) = strftime('%Y-%m', 'now')
    """).fetchone()
    
    # Get last 12 weeks stats
    row = db.execute("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(distance), 0) as total_distance,
            COALESCE(AVG(avg_pace), 0) as avg_pace,
            COALESCE(AVG(avg_heart_rate), 0) as avg_hr,
            MAX(start_time) as last_run
        FROM activities
        WHERE type='running'
          AND start_time >= datetime('now', '-84 days')
    """).fetchone()

    # Get all current month activities
    if include_strength:
        recent = db.execute("""
            SELECT id, name, type, distance, duration, avg_pace, avg_heart_rate, start_time,
                   avg_cadence, avg_ground_contact_time, avg_vertical_oscillation,
                   temperature, humidity, wind_speed, weather_condition
            FROM activities
            WHERE strftime('%Y-%m', start_time) = strftime('%Y-%m', 'now')
            ORDER BY start_time DESC
        """).fetchall()
    else:
        recent = db.execute("""
            SELECT id, name, type, distance, duration, avg_pace, avg_heart_rate, start_time,
                   avg_cadence, avg_ground_contact_time, avg_vertical_oscillation,
                   temperature, humidity, wind_speed, weather_condition
            FROM activities
            WHERE type != 'strength_training'
              AND strftime('%Y-%m', start_time) = strftime('%Y-%m', 'now')
            ORDER BY start_time DESC
        """).fetchall()
    db.close()

    recent_str = ''
    for r in recent:
        type_cn = {'running': '跑步', 'strength_training': '力量', 'cycling': '骑行', 'lap_swimming': '游泳'}.get(r['type'], r['type'] or '其他')
        dist_str = f'{r["distance"]/1000:.1f}km' if r['distance'] else '-'
        pace_str = _format_pace_str(r['avg_pace']) if r['type'] == 'running' else '-'
        hr_str = f'{round(r["avg_heart_rate"])}bpm' if r['avg_heart_rate'] else '-'
        extras = []
        if r['avg_cadence']: extras.append(f'步频{round(r["avg_cadence"])}')
        if r['avg_ground_contact_time']: extras.append(f'触地{round(r["avg_ground_contact_time"])}ms')
        if r['avg_vertical_oscillation']: extras.append(f'振幅{r["avg_vertical_oscillation"]:.1f}cm')
        weather_parts = []
        if r['temperature'] is not None: weather_parts.append(f'{r["temperature"]:.1f}°C')
        if r['humidity'] is not None: weather_parts.append(f'湿度{round(r["humidity"])}%')
        if r['wind_speed'] is not None: weather_parts.append(f'风速{r["wind_speed"]:.1f}km/h')
        if r['weather_condition']: weather_parts.append(r['weather_condition'])
        if weather_parts: extras.append('天气:' + '/'.join(weather_parts))
        extra_str = f' [{", ".join(extras)}]' if extras else ''
        recent_str += f"  {r['start_time'][:10]} {type_cn} {r['name']}: {dist_str} @{pace_str} 心率{hr_str}{extra_str}\n"

    # Build summary with both current month and 12-week stats
    current_month_str = f"本月: {current_month['count']}次跑步, 总跑量{current_month['total_distance']/1000:.1f}km"
    if current_month['avg_pace']:
        current_month_str += f", 平均配速{_format_pace_str(current_month['avg_pace'])}"
    if current_month['avg_hr']:
        current_month_str += f", 平均心率{current_month['avg_hr']:.0f}"
    
    summary = f"{current_month_str}\n最近12周: {row['count']}次跑步, 总跑量{row['total_distance']/1000:.1f}km, 平均配速{_format_pace_str(row['avg_pace'])}, 平均心率{row['avg_hr']:.0f}, 最近一次: {row['last_run'] or '无'}"
    return summary, recent_str


def _get_recent_split_context(limit=10, date_from=None, date_to=None):
    db = get_db()
    params = []
    sql = """
        SELECT id, name, start_time, distance, duration
        FROM activities
        WHERE type IN ({running_types})
    """
    running_placeholders, running_params = _running_type_sql()
    sql = sql.format(running_types=running_placeholders)
    params.extend(running_params)
    if date_from:
        sql += " AND start_time >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND start_time <= ?"
        params.append(date_to)
    sql += " ORDER BY start_time DESC LIMIT ?"
    params.append(limit)
    activities = [dict(r) for r in db.execute(sql, params).fetchall()]
    lines = []
    for activity in activities:
        splits = get_activity_splits(db, activity['id'])
        summary = build_split_summary(activity, splits)
        if summary:
            lines.append(summary)
    db.close()
    if not lines:
        return ''
    return '\n\n运动分段摘要（压缩后，仅供分析配速稳定性/心率漂移）:\n' + '\n'.join(lines)


def _normalize_date_to(value):
    if value and len(value) == 10:
        return value + ' 23:59:59'
    return value


def _running_type_sql():
    placeholders = ','.join('?' for _ in RUNNING_ACTIVITY_TYPES)
    return placeholders, list(RUNNING_ACTIVITY_TYPES)


def _get_health_summary():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM health_data ORDER BY date DESC LIMIT 7"
    ).fetchall()
    db.close()
    if not rows:
        return ''
    rows = list(reversed(rows))
    lines = ['\n近期健康数据:']
    for h in rows:
        parts = [h['date']]
        if h['hrv_avg']: parts.append(f"HRV={round(h['hrv_avg'])}ms")
        if h['sleep_score']: parts.append(f"睡眠={h['sleep_score']}分")
        if h['sleep_duration']: parts.append(f"{h['sleep_duration']}h")
        if h['resting_hr']: parts.append(f"静息HR={round(h['resting_hr'])}")
        if h['avg_stress']: parts.append(f"压力={round(h['avg_stress'])}")
        if h['body_battery_max']: parts.append(f"电量={h['body_battery_max']}/{h['body_battery_min'] or '-'}")
        lines.append('  ' + ' | '.join(parts))
    return '\n'.join(lines)


def _get_weather_summary():
    """Get weather data for AI chat context."""
    from backend.weather_service import get_weather, format_weather_for_chat
    
    city = get_config('weather_city', '上海市')
    try:
        weather = get_weather(city, days=3)
        if weather:
            return '\n' + format_weather_for_chat(weather)
    except Exception as e:
        print(f'Weather summary error: {e}')
    return ''


def _get_profile_info():
    age = get_config('profile_age', '')
    gender = get_config('profile_gender', '')
    height = get_config('profile_height', '')
    weight = get_config('profile_weight', '')
    resting_hr = get_config('profile_resting_hr', '')
    max_hr = get_config('profile_max_hr', '')
    race_goal = get_config('profile_race_goal', '')

    if not any([age, gender, height, weight, resting_hr, max_hr, race_goal]):
        return ''

    goal_map = {'5k': '5K', '10k': '10K', 'half_marathon': '半马', 'marathon': '全马'}
    parts = ['跑者基础信息:']
    if age: parts.append(f'- 年龄: {age}')
    if gender: parts.append(f'- 性别: {"男" if gender=="male" else "女"}')
    if height: parts.append(f'- 身高: {height}cm')
    if weight: parts.append(f'- 体重: {weight}kg')
    if resting_hr: parts.append(f'- 静息心率: {resting_hr}bpm')
    if max_hr: parts.append(f'- 最大心率: {max_hr}bpm')
    if race_goal: parts.append(f'- 跑步目标: {goal_map.get(race_goal, race_goal)}')

    # Add HR zones if both resting and max HR are set
    if resting_hr and max_hr:
        try:
            rhr = int(resting_hr)
            mhr = int(max_hr)
            reserve = mhr - rhr
            parts.append('')
            parts.append('心率区间（储备心率法，请直接引用）:')
            parts.append(f'  1恢复/热身: {rhr}~{round(rhr+reserve*0.60)}')
            parts.append(f'  2燃脂/轻松跑E: {round(rhr+reserve*0.60)}~{round(rhr+reserve*0.70)}')
            parts.append(f'  3有氧/马拉松M: {round(rhr+reserve*0.70)}~{round(rhr+reserve*0.80)}')
            parts.append(f'  4阈值T: {round(rhr+reserve*0.80)}~{round(rhr+reserve*0.90)}')
            parts.append(f'  5最大摄氧I: {round(rhr+reserve*0.90)}~{mhr}')
        except ValueError:
            pass

    return '\n'.join(parts) + '\n'


def _format_pace_str(seconds):
    if not seconds or seconds == 0:
        return '-'
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}/km"


def _get_llm_client():
    return LLMClient(
        base_url=get_config('llm_base_url'),
        api_key=get_config('llm_api_key'),
        model=get_config('llm_model')
    )


def create_app():
    app = Flask(
        __name__,
        static_folder='../frontend',
        static_url_path=''
    )

    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/api/ping')
    def ping():
        return jsonify({'status': 'ok'})

    @app.route('/api/sync', methods=['POST'])
    def sync():
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': '需要邮箱和密码'}), 400

        sync_health = data.get('sync_health', True)
        health_days = int(data.get('health_days', 14))
        result = sync_service.sync(data['email'], data['password'], sync_health, health_days)
        if 'error' in result:
            return jsonify(result), 401
        return jsonify(result)

    @app.route('/api/sync/backfill', methods=['POST'])
    def backfill_details():
        """Backfill running dynamics for existing activities without detail data."""
        from backend.garmin_client import GarminClient

        data = request.get_json() or {}
        limit_value = data.get('limit')
        backfill_all = bool(data.get('all')) or limit_value in (None, '', 0, '0', 'all')
        limit = None if backfill_all else int(limit_value)
        db = get_db()
        running_placeholders, running_params = _running_type_sql()
        query = f"""
            SELECT a.id, a.type, a.detail_json, COUNT(s.id) as split_count
            FROM activities a
            LEFT JOIN activity_splits s ON s.activity_id = a.id
            WHERE a.detail_json IS NULL
               OR (a.type IN ({running_placeholders}) AND s.id IS NULL)
            GROUP BY a.id
            ORDER BY a.start_time DESC
        """
        params = running_params
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        rows = db.execute(query, params).fetchall()
        db.close()

        if not rows:
            return jsonify({'status': 'ok', 'filled': 0, 'message': '所有活动已有详情数据'})

        gc = GarminClient()
        login = gc.login('', '')  # rely on saved tokens
        if not login.get('success'):
            return jsonify({'error': '需要先同步登录一次以保存 Token'}), 401

        filled = 0
        split_filled = 0
        for row in rows:
            try:
                detail = None
                detail_json = row['detail_json']
                if not detail_json:
                    detail = gc.fetch_activity_details(row['id'])
                if detail:
                    detail_json = detail.get('detail_json')
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
                        db2 = get_db()
                        vals.append(row['id'])
                        db2.execute(f"UPDATE activities SET {','.join(cols)} WHERE id=?", vals)
                        db2.commit()
                        db2.close()
                        filled += 1
                if is_running_activity_type(row['type']) and row['split_count'] == 0:
                    splits = normalize_official_splits(gc.fetch_activity_splits(row['id']), source='garmin')
                    useful_splits = [s for s in splits if is_meaningful_split(s)]
                    if not useful_splits and detail_json:
                        useful_splits = splits_from_detail_json(detail_json)
                    if useful_splits:
                        db3 = get_db()
                        save_splits(db3, row['id'], useful_splits)
                        db3.commit()
                        db3.close()
                        split_filled += 1
            except Exception:
                pass

        return jsonify({'status': 'ok', 'filled': filled, 'split_filled': split_filled, 'total': len(rows), 'all': backfill_all})

    @app.route('/api/sync/backfill_weather', methods=['POST'])
    def backfill_weather():
        """Backfill weather data for existing activities without weather info."""
        from backend.garmin_client import GarminClient

        data = request.get_json() or {}
        limit = int(data.get('limit', 50))
        db = get_db()
        rows = db.execute(
            "SELECT id FROM activities WHERE weather_json IS NULL ORDER BY start_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
        db.close()

        if not rows:
            return jsonify({'status': 'ok', 'filled': 0, 'message': '所有活动已有天气数据'})

        gc = GarminClient()
        login = gc.login('', '')
        if not login.get('success'):
            return jsonify({'error': '需要先同步登录一次以保存 Token'}), 401

        filled = 0
        for row in rows:
            try:
                weather = gc.fetch_activity_weather(row['id'])
                if weather:
                    cols = []
                    vals = []
                    for k in ['temperature', 'humidity', 'wind_speed', 'weather_condition', 'weather_json']:
                        v = weather.get(k)
                        if v is not None:
                            cols.append(f"{k}=?")
                            vals.append(v)
                    if cols:
                        db2 = get_db()
                        vals.append(row['id'])
                        db2.execute(f"UPDATE activities SET {','.join(cols)} WHERE id=?", vals)
                        db2.commit()
                        db2.close()
                        filled += 1
            except Exception:
                pass

        return jsonify({'status': 'ok', 'filled': filled, 'total': len(rows)})

    @app.route('/api/health/sync', methods=['POST'])
    def health_sync():
        """Fetch health data (HRV/sleep/stress) for recent days."""
        from backend.garmin_client import GarminClient
        from datetime import date, timedelta

        data = request.get_json() or {}
        days = int(data.get('days', 7))

        gc = GarminClient()
        login = gc.login('', '')
        if not login.get('success'):
            return jsonify({'error': '需要先同步登录一次以保存 Token'}), 401

        fetched = 0
        for i in range(days):
            d = (date.today() - timedelta(days=i)).isoformat()
            try:
                hd = gc.fetch_health_data(d)
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

        return jsonify({'status': 'ok', 'fetched': fetched, 'days': days})

    @app.route('/api/health')
    def health_data():
        days = request.args.get('days')
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        
        db = get_db()
        
        if date_from and date_to:
            # Use date range if provided
            rows = db.execute(
                "SELECT * FROM health_data WHERE date >= ? AND date <= ? ORDER BY date",
                (date_from, date_to)
            ).fetchall()
        elif days:
            # Fall back to days parameter
            rows = db.execute(
                "SELECT * FROM health_data ORDER BY date DESC LIMIT ?",
                (int(days),)
            ).fetchall()
            rows = list(reversed(rows))
        else:
            # Default: last 14 days
            rows = db.execute(
                "SELECT * FROM health_data ORDER BY date DESC LIMIT 14"
            ).fetchall()
            rows = list(reversed(rows))
        
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/activities')
    def list_activities():
        activity_type = request.args.get('type')
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        search = request.args.get('q')

        db = get_db()
        query = """SELECT id, name, type, start_time, duration, distance,
                          avg_heart_rate, max_heart_rate, avg_pace, elevation_gain
                   FROM activities WHERE 1=1"""
        params = []

        if activity_type:
            if activity_type == 'running':
                running_placeholders, running_params = _running_type_sql()
                query += f" AND type IN ({running_placeholders})"
                params.extend(running_params)
            else:
                query += " AND type=?"
                params.append(activity_type)
        if date_from:
            query += " AND start_time >= ?"
            params.append(date_from)
        if date_to:
            query += " AND start_time <= ?"
            params.append(_normalize_date_to(date_to))
        if search:
            query += " AND name LIKE ?"
            params.append(f'%{search}%')

        query += " ORDER BY start_time DESC LIMIT 500"

        rows = db.execute(query, params).fetchall()
        db.close()

        return jsonify([dict(r) for r in rows])

    @app.route('/api/activity/<int:activity_id>')
    def activity_detail(activity_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM activities WHERE id=?",
            (activity_id,)
        ).fetchone()
        db.close()

        if not row:
            return jsonify({'error': '活动不存在'}), 404

        result = dict(row)
        if result.get('raw_json'):
            try:
                result['raw_json'] = json.loads(result['raw_json'])
            except json.JSONDecodeError:
                pass
        return jsonify(result)

    @app.route('/api/activities/<int:activity_id>/splits')
    def activity_splits(activity_id):
        db = get_db()
        activity = db.execute(
            "SELECT id FROM activities WHERE id=?",
            (activity_id,)
        ).fetchone()
        if not activity:
            db.close()
            return jsonify({'error': 'not found'}), 404
        splits = get_activity_splits(db, activity_id)
        db.close()
        return jsonify(splits)

    @app.route('/api/vdot')
    def vdot_endpoint():
        from backend.report_generator import calc_vdot, predict_time_str, _calc_v_from_vo2, _sec_to_pace, TRAINING_PACES, RACE_DISTANCES

        db = get_db()
        best_runs = db.execute("""
            SELECT name, distance, duration, start_time
            FROM activities WHERE type='running' AND distance >= 5000 AND duration > 0
            ORDER BY distance ASC
        """).fetchall()

        best_vdot = 0
        best_source = ''
        for run in best_runs:
            pace = run['duration'] / (run['distance'] / 1000)
            if pace > 600:
                continue
            vd = calc_vdot(run['distance'], run['duration'])
            if vd > best_vdot:
                best_vdot = vd
                best_source = f"{run['name']} ({run['distance']/1000:.1f}km)"

        best_5k = db.execute("""
            SELECT name, duration FROM activities
            WHERE type='running' AND distance >= 4800 AND distance <= 5200 AND duration > 0
            ORDER BY duration ASC LIMIT 1
        """).fetchone()
        db.close()

        result = {'vdot': round(best_vdot, 1) if best_vdot else 0, 'source': best_source, 'predictions': {}, 'pace_zones': {}, 'hr_zones': {}}

        if best_vdot > 0:
            vmax = _calc_v_from_vo2(best_vdot)
            race_distances = {'5K': 5000, '10K': 10000, '半马': 21097.5, '全马': 42195}
            for dist_name, dist_m in race_distances.items():
                result['predictions'][dist_name] = predict_time_str(best_vdot, dist_m)

            if vmax > 0:
                bp = 1000 / vmax * 60
                training_paces = [
                    ('轻松跑 E', (0.72, 0.82)),
                    ('马拉松配速 M', (0.82, 0.90)),
                    ('乳酸阈值 T', (0.90, 0.96)),
                    ('间歇跑 I', (0.96, 1.02)),
                    ('重复跑 R', (1.02, 1.10)),
                ]
                for name, (lo, hi) in training_paces:
                    result['pace_zones'][name] = {
                        'fast': _sec_to_pace(bp / hi),
                        'slow': _sec_to_pace(bp / lo)
                    }

            if best_5k:
                duration = best_5k['duration']
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                result['best_5k'] = f"{best_5k['name']} ({minutes}:{seconds:02d})"

        # HR zones from profile
        resting_hr = get_config('profile_resting_hr', '')
        max_hr = get_config('profile_max_hr', '')
        if resting_hr and max_hr:
            try:
                rhr = int(resting_hr)
                mhr = int(max_hr)
                reserve = mhr - rhr
                result['hr_zones'] = {
                    '1 (恢复)': f"{rhr} ~ {round(rhr + reserve*0.60)}",
                    '2 (燃脂/轻松跑)': f"{round(rhr + reserve*0.60)} ~ {round(rhr + reserve*0.70)}",
                    '3 (有氧/马拉松)': f"{round(rhr + reserve*0.70)} ~ {round(rhr + reserve*0.80)}",
                    '4 (阈值)': f"{round(rhr + reserve*0.80)} ~ {round(rhr + reserve*0.90)}",
                    '5 (最大摄氧)': f"{round(rhr + reserve*0.90)} ~ {mhr}",
                }
            except ValueError:
                pass

        return jsonify(result)

    @app.route('/api/stats')
    def stats():
        from backend.report_generator import calc_vdot, _calc_v_from_vo2, _sec_to_pace, TRAINING_PACES

        period = request.args.get('period', 'monthly')
        date_from = request.args.get('from', '1970-01-01')
        date_to = request.args.get('to', '2099-12-31')
        db = get_db()

        overview = db.execute("""
            SELECT
                COUNT(*) as total_runs,
                COALESCE(SUM(distance), 0) as total_distance,
                COALESCE(SUM(duration), 0) as total_duration,
                COALESCE(AVG(avg_heart_rate), 0) as avg_hr,
                COALESCE(AVG(avg_pace), 0) as avg_pace
            FROM activities
            WHERE type='running'
              AND start_time >= ? AND start_time <= ?
        """, (date_from, date_to)).fetchone()

        monthly = db.execute("""
            SELECT
                strftime('%Y-%m', start_time) as month,
                COUNT(*) as count,
                COALESCE(SUM(distance), 0) as distance,
                COALESCE(SUM(duration), 0) as duration,
                COALESCE(AVG(avg_pace), 0) as avg_pace
            FROM activities
            WHERE type='running'
              AND start_time >= ? AND start_time <= ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """, (date_from, date_to)).fetchall()

        pace_rows = db.execute("""
            SELECT id, avg_pace, distance, duration
            FROM activities
            WHERE type='running' AND avg_pace > 0
              AND start_time >= ? AND start_time <= ?
            ORDER BY avg_pace
        """, (date_from, date_to)).fetchall()

        best_vdot = 0
        vdot_rows = db.execute("""
            SELECT distance, duration
            FROM activities
            WHERE type='running' AND distance >= 5000 AND duration > 0
        """).fetchall()
        for row in vdot_rows:
            if row['distance'] and row['duration']:
                pace = row['duration'] / (row['distance'] / 1000)
                if pace <= 600:
                    best_vdot = max(best_vdot, calc_vdot(row['distance'], row['duration']))

        pace_dist = []
        if best_vdot > 0:
            vmax = _calc_v_from_vo2(best_vdot)
            zone_defs = []
            if vmax > 0:
                base_pace = 1000 / vmax * 60
                training_paces = [
                    ('轻松跑 E', (0.72, 0.82)),
                    ('马拉松配速 M', (0.82, 0.90)),
                    ('乳酸阈值 T', (0.90, 0.96)),
                    ('间歇跑 I', (0.96, 1.02)),
                    ('重复跑 R', (1.02, 1.10)),
                ]
                for name, (lo, hi) in training_paces:
                    fast = base_pace / hi
                    slow = base_pace / lo
                    zone_defs.append({
                        'pace_range': f'{name} {_sec_to_pace(fast)}-{_sec_to_pace(slow)}',
                        'count': 0,
                        'fast': fast,
                        'slow': slow,
                    })

            def add_zone_distance(pace, distance):
                distance_km = (distance or 0) / 1000
                if not pace or distance_km <= 0 or not zone_defs:
                    return
                target = None
                for zone in zone_defs:
                    if zone['fast'] <= pace <= zone['slow']:
                        target = zone
                        break
                if not target:
                    fastest = min(zone_defs, key=lambda z: z['fast'])
                    slowest = max(zone_defs, key=lambda z: z['slow'])
                    if pace < fastest['fast']:
                        target = fastest
                    elif pace > slowest['slow']:
                        target = slowest
                    else:
                        target = min(
                            zone_defs,
                            key=lambda z: min(abs(pace - z['fast']), abs(pace - z['slow']))
                        )
                target['count'] += distance_km

            for row in pace_rows:
                activity_distance = row['distance'] or 0
                split_rows = db.execute("""
                    SELECT distance, avg_pace
                    FROM activity_splits
                    WHERE activity_id=? AND avg_pace > 0 AND distance >= 200
                    ORDER BY split_index
                """, (row['id'],)).fetchall()
                split_total = sum(s['distance'] or 0 for s in split_rows)
                use_splits = (
                    split_rows and activity_distance > 0
                    and activity_distance * 0.5 <= split_total <= activity_distance * 1.2
                )
                if use_splits:
                    for split in split_rows:
                        add_zone_distance(split['avg_pace'], split['distance'])
                else:
                    add_zone_distance(row['avg_pace'], activity_distance)

            pace_dist = [
                {'pace_range': z['pace_range'], 'count': round(z['count'], 2)}
                for z in zone_defs
            ]
        else:
            rows = db.execute("""
                SELECT
                    CASE
                        WHEN avg_pace < 240 THEN '<4:00'
                        WHEN avg_pace < 270 THEN '4:00-4:30'
                        WHEN avg_pace < 300 THEN '4:30-5:00'
                        WHEN avg_pace < 330 THEN '5:00-5:30'
                        WHEN avg_pace < 360 THEN '5:30-6:00'
                        WHEN avg_pace < 420 THEN '6:00-7:00'
                        ELSE '>7:00'
                    END as pace_range,
                    ROUND(COALESCE(SUM(distance), 0) / 1000.0, 2) as count
                FROM activities
                WHERE type='running' AND avg_pace > 0
                  AND start_time >= ? AND start_time <= ?
                GROUP BY pace_range
                ORDER BY MIN(avg_pace)
            """, (date_from, date_to)).fetchall()
            pace_dist = [dict(r) for r in rows]

        db.close()

        return jsonify({
            'overview': dict(overview),
            'monthly': [dict(r) for r in reversed(monthly)],
            'pace_distribution': pace_dist,
        })

    @app.route('/api/trends')
    def trends():
        from backend.report_generator import calc_vdot
        from backend.fitness_metrics import estimate_vo2max_from_activity, calc_median
        from datetime import datetime, timedelta

        date_from = request.args.get('from', '1970-01-01')
        date_to = request.args.get('to', '2099-12-31')
        bucket = request.args.get('bucket', 'week')

        if bucket not in ('day', 'week', 'month'):
            bucket = 'week'

        # Get HR config for VO2max estimation
        resting_hr_config = get_config('profile_resting_hr', '')
        max_hr_config = get_config('profile_max_hr', '')
        try:
            config_resting_hr = float(resting_hr_config) if resting_hr_config else None
        except (ValueError, TypeError):
            config_resting_hr = None
        try:
            config_max_hr = float(max_hr_config) if max_hr_config else None
        except (ValueError, TypeError):
            config_max_hr = None

        db = get_db()

        # Get running activities
        activities = db.execute("""
            SELECT id, name, distance, duration, avg_pace, avg_heart_rate,
                   elevation_gain, training_effect, start_time, vo2max
            FROM activities
            WHERE type='running'
              AND start_time >= ? AND start_time <= ?
            ORDER BY start_time
        """, (date_from, date_to + ' 23:59:59')).fetchall()

        # Get health data (including vo2max)
        health_data = db.execute("""
            SELECT date, hrv_avg, sleep_score, resting_hr, vo2max
            FROM health_data
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, (date_from, date_to)).fetchall()

        db.close()

        # Convert to dicts
        activities = [dict(a) for a in activities]
        health_map = {}
        for h in health_data:
            h = dict(h)
            health_map[h['date']] = h

        # Bucket activities by time period
        def get_bucket_key(dt_str, bucket):
            try:
                dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                try:
                    dt = datetime.strptime(dt_str[:10], '%Y-%m-%d')
                except (ValueError, TypeError):
                    return None
            if bucket == 'day':
                return dt.strftime('%Y-%m-%d')
            elif bucket == 'week':
                # ISO week: Monday as start
                start = dt - timedelta(days=dt.weekday())
                return start.strftime('%Y-%m-%d')
            else:  # month
                return dt.strftime('%Y-%m')

        buckets = {}
        for a in activities:
            key = get_bucket_key(a['start_time'], bucket)
            if not key:
                continue
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(a)

        # Build series
        series = []
        sorted_keys = sorted(buckets.keys())

        for key in sorted_keys:
            acts = buckets[key]
            count = len(acts)
            total_distance = sum(a['distance'] or 0 for a in acts)
            total_duration = sum(a['duration'] or 0 for a in acts)
            total_elevation = sum(a['elevation_gain'] or 0 for a in acts)

            # Weighted average pace (total_duration / total_distance)
            avg_pace = (total_duration / (total_distance / 1000)) if total_distance > 0 else None

            # Average heart rate (weighted by duration)
            hr_sum = 0
            hr_dur = 0
            for a in acts:
                if a['avg_heart_rate'] and a['duration']:
                    hr_sum += a['avg_heart_rate'] * a['duration']
                    hr_dur += a['duration']
            avg_hr = (hr_sum / hr_dur) if hr_dur > 0 else None

            # Average training effect
            te_vals = [a['training_effect'] for a in acts if a['training_effect']]
            avg_te = (sum(te_vals) / len(te_vals)) if te_vals else None

            # Best VDOT in this bucket
            best_vdot = 0
            for a in acts:
                if a['distance'] and a['distance'] >= 5000 and a['duration'] and a['duration'] > 0:
                    pace = a['duration'] / (a['distance'] / 1000)
                    if pace <= 600:  # not slower than 10:00/km
                        vd = calc_vdot(a['distance'], a['duration'])
                        if vd > best_vdot:
                            best_vdot = vd

            # VO2max estimation using ACSM + HR reserve (median of valid activities)
            vo2max_estimates = []
            bucket_resting_hr = config_resting_hr
            bucket_max_hr = config_max_hr

            # Try to get resting HR from health data in this bucket
            if not bucket_resting_hr and rhr_vals:
                bucket_resting_hr = sum(rhr_vals) / len(rhr_vals)

            for a in acts:
                if a['avg_heart_rate'] and a['distance'] and a['duration']:
                    est = estimate_vo2max_from_activity(
                        a['distance'], a['duration'],
                        a['avg_heart_rate'],
                        bucket_resting_hr,
                        bucket_max_hr
                    )
                    if est is not None:
                        vo2max_estimates.append(est)

            vo2max_est = round(calc_median(vo2max_estimates), 2) if vo2max_estimates else None

            # Garmin VO2max from activities (if available)
            vo2max_vals = [a['vo2max'] for a in acts if a['vo2max'] and a['vo2max'] > 0]
            garmin_vo2max = round(sum(vo2max_vals) / len(vo2max_vals), 2) if vo2max_vals else None

            # Also check health data for Garmin VO2max
            if not garmin_vo2max:
                health_vo2_vals = []
                for a in acts:
                    try:
                        dt = datetime.strptime(a['start_time'][:10], '%Y-%m-%d')
                        date_key = dt.strftime('%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue
                    hd = health_map.get(date_key)
                    if hd and hd.get('vo2max') and hd['vo2max'] > 0:
                        health_vo2_vals.append(hd['vo2max'])
                if health_vo2_vals:
                    garmin_vo2max = round(sum(health_vo2_vals) / len(health_vo2_vals), 2)

            # Health data (aggregate by matching dates)
            hrv_vals = []
            sleep_vals = []
            rhr_vals = []
            for a in acts:
                try:
                    dt = datetime.strptime(a['start_time'][:10], '%Y-%m-%d')
                    date_key = dt.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    continue
                hd = health_map.get(date_key)
                if hd:
                    if hd.get('hrv_avg'):
                        hrv_vals.append(hd['hrv_avg'])
                    if hd.get('sleep_score'):
                        sleep_vals.append(hd['sleep_score'])
                    if hd.get('resting_hr'):
                        rhr_vals.append(hd['resting_hr'])

            # For week/month buckets, also aggregate health by dates in range
            if bucket != 'day':
                try:
                    start_dt = datetime.strptime(key, '%Y-%m-%d')
                    if bucket == 'week':
                        end_dt = start_dt + timedelta(days=6)
                    else:  # month
                        if start_dt.month == 12:
                            end_dt = start_dt.replace(year=start_dt.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            end_dt = start_dt.replace(month=start_dt.month + 1, day=1) - timedelta(days=1)
                    current = start_dt
                    while current <= end_dt:
                        hd = health_map.get(current.strftime('%Y-%m-%d'))
                        if hd:
                            if hd.get('hrv_avg') and hd['hrv_avg'] not in hrv_vals:
                                hrv_vals.append(hd['hrv_avg'])
                            if hd.get('sleep_score') and hd['sleep_score'] not in sleep_vals:
                                sleep_vals.append(hd['sleep_score'])
                            if hd.get('resting_hr') and hd['resting_hr'] not in rhr_vals:
                                rhr_vals.append(hd['resting_hr'])
                        current += timedelta(days=1)
                except (ValueError, TypeError):
                    pass

            # Calculate recovery score for this bucket
            recovery_score = None
            recovery_unit = None
            if hrv_vals:
                recovery_score = round(sum(hrv_vals) / len(hrv_vals), 1)
                recovery_unit = 'ms'
            elif sleep_vals:
                recovery_score = round(sum(sleep_vals) / len(sleep_vals), 1)
                recovery_unit = '%'
            elif rhr_vals:
                recovery_score = round(sum(rhr_vals) / len(rhr_vals), 1)
                recovery_unit = 'bpm'

            series.append({
                'period': key,
                'count': count,
                'total_distance': round(total_distance, 1),
                'total_duration': round(total_duration, 1),
                'avg_pace': round(avg_pace, 1) if avg_pace else None,
                'avg_hr': round(avg_hr, 1) if avg_hr else None,
                'total_elevation': round(total_elevation, 1),
                'avg_training_effect': round(avg_te, 2) if avg_te else None,
                'vdot': round(best_vdot, 1) if best_vdot > 0 else None,
                'vo2max_estimate': vo2max_est,
                'garmin_vo2max': garmin_vo2max,
                'hrv_avg': round(sum(hrv_vals) / len(hrv_vals), 1) if hrv_vals else None,
                'sleep_score': round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else None,
                'resting_hr': round(sum(rhr_vals) / len(rhr_vals), 1) if rhr_vals else None,
                'recovery_score': recovery_score,
                'recovery_unit': recovery_unit,
            })

        # Summary stats
        total_distance = sum(s['total_distance'] for s in series)
        total_count = sum(s['count'] for s in series)
        total_duration = sum(s['total_duration'] for s in series)
        week_count = len(set(
            get_bucket_key(a['start_time'], 'week')
            for a in activities
            if get_bucket_key(a['start_time'], 'week')
        ))
        weekly_avg = (total_distance / week_count / 1000) if week_count > 0 else 0
        overall_pace = (total_duration / (total_distance / 1000)) if total_distance > 0 else None
        hr_vals = [a['avg_heart_rate'] for a in activities if a['avg_heart_rate']]
        overall_hr = (sum(hr_vals) / len(hr_vals)) if hr_vals else None

        # Best VDOT overall
        best_vdot_overall = 0
        for s in series:
            if s['vdot'] and s['vdot'] > best_vdot_overall:
                best_vdot_overall = s['vdot']

        # VO2max estimate for summary: median of all bucket estimates
        all_vo2_estimates = [s['vo2max_estimate'] for s in series if s['vo2max_estimate']]
        summary_vo2max = round(calc_median(all_vo2_estimates), 2) if all_vo2_estimates else None

        # Garmin VO2max for summary: average of all bucket values
        all_garmin_vo2 = [s['garmin_vo2max'] for s in series if s['garmin_vo2max']]
        summary_garmin_vo2max = round(sum(all_garmin_vo2) / len(all_garmin_vo2), 2) if all_garmin_vo2 else None

        # Recovery index: aggregate from all health data in range
        all_hrv = [s['hrv_avg'] for s in series if s['hrv_avg']]
        all_sleep = [s['sleep_score'] for s in series if s['sleep_score']]
        all_rhr = [s['resting_hr'] for s in series if s['resting_hr']]
        recovery_index = None
        if all_hrv:
            recovery_index = round(sum(all_hrv) / len(all_hrv), 1)
        elif all_sleep:
            recovery_index = round(sum(all_sleep) / len(all_sleep), 1)
        elif all_rhr:
            # Lower resting HR is better, use as inverse indicator
            recovery_index = round(sum(all_rhr) / len(all_rhr), 1)

        summary = {
            'vdot': round(best_vdot_overall, 1) if best_vdot_overall > 0 else None,
            'vo2max_estimate': summary_vo2max,
            'garmin_vo2max': summary_garmin_vo2max,
            'total_distance': round(total_distance / 1000, 1),
            'weekly_avg': round(weekly_avg, 1),
            'avg_pace': round(overall_pace, 1) if overall_pace else None,
            'avg_hr': round(overall_hr, 1) if overall_hr else None,
            'recovery_index': recovery_index,
            'recovery_unit': 'ms' if all_hrv else ('%' if all_sleep else 'bpm'),
        }

        return jsonify({
            'range': {'from': date_from, 'to': date_to, 'bucket': bucket},
            'summary': summary,
            'series': series,
        })

    @app.route('/api/heatmap')
    def heatmap():
        from backend.route_service import RouteService

        date_from = request.args.get('from')
        date_to = request.args.get('to')
        mode = request.args.get('mode', 'distance')
        city = request.args.get('city')

        if mode not in ('distance', 'count', 'pace'):
            mode = 'distance'

        route_service = RouteService()
        try:
            data = route_service.get_heatmap_data(date_from, date_to, mode, city)
            return jsonify(data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/heatmap/backfill', methods=['POST'])
    def heatmap_backfill():
        from backend.route_service import RouteService

        data = request.get_json() or {}
        limit = int(data.get('limit', 50))

        route_service = RouteService()
        try:
            result = route_service.backfill_routes(limit)
            return jsonify({'status': 'ok', **result})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/chat/sessions')
    def chat_sessions():
        return jsonify(chat_service.get_sessions())

    @app.route('/api/chat/sessions', methods=['POST'])
    def chat_create_session():
        session_id = chat_service.create_session()
        return jsonify({'session_id': session_id})

    @app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
    def chat_delete_session(session_id):
        chat_service.delete_session(session_id)
        return jsonify({'status': 'ok'})

    @app.route('/api/chat/ask', methods=['POST'])
    def chat_ask():
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': '需要提供问题'}), 400

        question = data['question']
        session_id = data.get('session_id', '')
        if not session_id:
            session_id = chat_service.create_session()
        include_strength = data.get('include_strength', False)
        summary, recent_activities = _get_training_summary(include_strength)
        health_summary = _get_health_summary()
        split_summary = _get_recent_split_context(limit=10)
        weather_summary = _get_weather_summary()
        context_snapshot = summary + health_summary + split_summary + weather_summary
        recent = chat_service.get_history(session_id=session_id) if session_id else []
        profile_info = _get_profile_info()
        messages = chat_service.build_messages(session_id, question, context_snapshot, recent,
                                                recent_activities, profile_info)

        llm = _get_llm_client()
        chat_service.save_message(session_id, 'user', question, context_snapshot)
        assistant_msg_id = chat_service.save_message(session_id, 'assistant', '', context_snapshot)

        def generate():
            full_answer = ''
            try:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
                for chunk in llm.chat_stream(messages):
                    full_answer += chunk
                    chat_service.update_message(assistant_msg_id, full_answer)
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            except Exception as e:
                chat_service.update_message(assistant_msg_id, f"错误：{str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')

    @app.route('/api/chat/history')
    def chat_history():
        session_id = request.args.get('session_id')
        keyword = request.args.get('q')
        if keyword:
            result = chat_service.search_history(keyword)
        else:
            result = chat_service.get_history(session_id=session_id)
        return jsonify(result)

    @app.route('/api/chat/delete/<int:msg_id>', methods=['DELETE'])
    def chat_delete(msg_id):
        chat_service.delete_message(msg_id)
        return jsonify({'status': 'ok'})

    @app.route('/api/chat/clear', methods=['DELETE'])
    def chat_clear():
        chat_service.clear_all()
        return jsonify({'status': 'ok'})

    @app.route('/api/config', methods=['GET', 'POST'])
    def config_handler():
        from backend.config import get_all_config, set_config
        if request.method == 'GET':
            config = get_all_config()
            api_key = config.get('llm_api_key', '')
            if api_key and len(api_key) > 8:
                config['llm_api_key'] = api_key[:4] + '****' + api_key[-4:]
            elif api_key:
                config['llm_api_key'] = '****'
            else:
                config['llm_api_key'] = ''
            return jsonify(config)

        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': '需要配置数据'}), 400

            for key in ['llm_base_url', 'llm_api_key', 'llm_model', 'report_rounds',
                        'profile_age', 'profile_gender', 'profile_height', 'profile_weight',
                        'profile_resting_hr', 'profile_max_hr', 'profile_race_goal']:
                if key in data and data[key] is not None and data[key] != '':
                    if key == 'llm_api_key' and '****' in str(data[key]):
                        continue
                    set_config(key, data[key])

            return jsonify({'status': 'ok'})

    @app.route('/api/report/generate', methods=['POST'])
    def generate_report():
        from backend.report_generator import ReportGenerator, calc_vdot
        import uuid
        import threading

        data = request.get_json() or {}
        date_from = data.get('from', '2020-01-01')
        date_to_display = data.get('to', '2099-12-31')
        date_to = _normalize_date_to(date_to_display)

        db = get_db()
        rows = db.execute("""
            SELECT
                COUNT(*) as total_runs,
                COALESCE(SUM(distance), 0) as total_distance,
                COALESCE(SUM(duration), 0) as total_duration,
                COALESCE(AVG(avg_pace), 0) as avg_pace,
                COALESCE(AVG(avg_heart_rate), 0) as avg_hr,
                COALESCE(SUM(elevation_gain), 0) as total_elevation
            FROM activities
            WHERE type='running'
            AND start_time >= ? AND start_time <= ?
        """, (date_from, date_to)).fetchone()

        has_strength = db.execute(
            "SELECT COUNT(*) as c FROM activities WHERE type='strength_training'"
        ).fetchone()['c'] > 0

        performances = {}
        # Find best VDOT from runs >= 3K (exclude short sprints)
        best_runs = db.execute("""
            SELECT name, distance, duration, start_time
            FROM activities
            WHERE type='running' AND distance >= 5000 AND duration > 0
              AND start_time >= ? AND start_time <= ?
            ORDER BY distance ASC
        """, (date_from, date_to)).fetchall()

        if best_runs:
            best_vdot = 0
            best_source = ''
            best_5k_time = None
            for run in best_runs:
                pace = run['duration'] / (run['distance'] / 1000)
                if pace > 600:  # slower than 10:00/km, skip walks
                    continue
                vd = calc_vdot(run['distance'], run['duration'])
                if vd > best_vdot:
                    best_vdot = vd
                    best_source = f"{run['name']} ({run['distance']/1000:.1f}km, {run['duration']/60:.1f}min)"
            # Find best 5K specifically
            best_5k = db.execute("""
                SELECT name, duration, start_time
                FROM activities
                WHERE type='running' AND distance >= 4800 AND distance <= 5200 AND duration > 0
                ORDER BY duration ASC LIMIT 1
            """).fetchone()
            if best_5k:
                duration = best_5k['duration']
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                best_5k_time = f"{best_5k['name']} ({minutes}:{seconds:02d}, {best_5k['start_time'][:10]})"

            if best_vdot > 0:
                performances['vdot'] = best_vdot
                performances['source'] = best_source
                if best_5k_time:
                    performances['best_5k'] = best_5k_time

        recent = db.execute("""
            SELECT name, type, distance, duration, avg_pace, start_time
            FROM activities
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time DESC LIMIT 10
        """, (date_from, date_to)).fetchall()
        recent_str = '; '.join(
            f"{r['start_time'][:10]} {r['name']}: {r['distance']/1000:.1f}km @{r['avg_pace']:.0f}s/km" if r['distance'] else f"{r['start_time'][:10]} {r['name']}"
            for r in reversed(recent)
        ) if recent else '无'

        # Full individual running list for detailed analysis
        activity_rows = db.execute("""
            SELECT name, type, distance, duration, avg_pace, avg_heart_rate, max_heart_rate,
                   elevation_gain, start_time,
                   avg_cadence, avg_ground_contact_time, avg_vertical_oscillation, avg_stride_length,
                   training_effect, vo2max,
                   temperature, humidity, wind_speed, weather_condition
            FROM activities
            WHERE type='running' AND start_time >= ? AND start_time <= ?
            ORDER BY start_time DESC
        """, (date_from, date_to)).fetchall()
        individual_activities = [dict(r) for r in reversed(activity_rows)]

        profile = {
            'age': get_config('profile_age', ''),
            'gender': get_config('profile_gender', ''),
            'height': get_config('profile_height', ''),
            'weight': get_config('profile_weight', ''),
            'resting_hr': get_config('profile_resting_hr', ''),
            'max_hr': get_config('profile_max_hr', ''),
            'race_goal': get_config('profile_race_goal', ''),
        }
        # Health data for report context
        health_rows = db.execute(
            "SELECT * FROM health_data ORDER BY date DESC LIMIT 14"
        ).fetchall()
        db.close()

        training_data = dict(rows)
        training_data['has_strength'] = has_strength
        training_data['date_range'] = f'{date_from} ~ {date_to_display}'
        training_data['performances'] = performances
        training_data['profile'] = profile
        training_data['recent'] = recent_str
        training_data['activities'] = individual_activities
        training_data['split_context'] = _get_recent_split_context(limit=30, date_from=date_from, date_to=date_to)
        training_data['health_data'] = [dict(r) for r in reversed(health_rows)]

        task_id = str(uuid.uuid4())[:8]
        report_tasks[task_id] = {'status': 'running', 'progress': '准备中...', 'result': None}

        def run():
            try:
                generator = ReportGenerator(
                    base_url=get_config('llm_base_url'),
                    api_key=get_config('llm_api_key'),
                    model=get_config('llm_model'),
                    rounds=int(get_config('report_rounds', '4'))
                )
                for update in generator.generate_stream(training_data):
                    if update['status'] == 'done':
                        report_tasks[task_id]['result'] = update['report']
                        report_tasks[task_id]['status'] = 'done'
                        report_tasks[task_id]['progress'] = '完成'
                        _save_report(task_id, date_from, date_to_display, update['report'])
                    else:
                        report_tasks[task_id]['progress'] = update.get('phase', '')
                report_tasks[task_id]['status'] = 'done'
            except Exception as e:
                report_tasks[task_id]['status'] = 'error'
                report_tasks[task_id]['progress'] = str(e)

        threading.Thread(target=run, daemon=True).start()

        return jsonify({'task_id': task_id})

    @app.route('/api/report/status/<task_id>')
    def report_status(task_id):
        task = report_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify({
            'status': task['status'],
            'progress': task['progress']
        })

    @app.route('/api/report/result/<task_id>')
    def report_result(task_id):
        task = report_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        if task['status'] == 'error':
            return jsonify({'error': task['progress']}), 500
        if task['status'] != 'done':
            return jsonify({'status': 'pending', 'progress': task['progress']})
        return jsonify({'report': task['result']})

    @app.route('/api/reports')
    def list_reports():
        db = get_db()
        rows = db.execute(
            "SELECT id, title, date_from, date_to, created_at FROM reports ORDER BY created_at DESC"
        ).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/report/<int:report_id>')
    def get_report(report_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM reports WHERE id=?", (report_id,)
        ).fetchone()
        db.close()
        if not row:
            return jsonify({'error': '报告不存在'}), 404
        return jsonify(dict(row))

    @app.route('/api/report/<int:report_id>', methods=['DELETE'])
    def delete_report(report_id):
        db = get_db()
        db.execute("DELETE FROM reports WHERE id=?", (report_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'ok'})

    with app.app_context():
        init_db()
        _init_sync_service()

    return app


report_tasks = {}


def _save_report(task_id, date_from, date_to, content):
    lines = content.split('\n')
    title = '训练报告'
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# ') and '训练' in stripped:
            title = stripped.lstrip('# ').strip()
            break
    try:
        db = get_db()
        db.execute(
            "INSERT INTO reports (title, date_from, date_to, content) VALUES (?, ?, ?, ?)",
            (title, date_from, date_to, content)
        )
        db.commit()
        db.close()
    except Exception:
        pass


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)
