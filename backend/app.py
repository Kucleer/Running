import os
import json
from flask import Flask, send_from_directory, jsonify, request, Response
from backend.database import init_db, get_db
from backend.sync_service import SyncService
from backend.chat_service import ChatService
from backend.llm_client import LLMClient
from backend.config import get_config


sync_service = None
chat_service = ChatService()


def _init_sync_service():
    global sync_service
    from backend.database import _get_db_path
    tokenstore = os.path.join(os.path.dirname(_get_db_path()), 'garmin_tokens')
    sync_service = SyncService(tokenstore=tokenstore)


def _get_training_summary():
    db = get_db()
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

    recent = db.execute("""
        SELECT name, type, distance, duration, avg_pace, avg_heart_rate, start_time,
               avg_cadence, avg_ground_contact_time, avg_vertical_oscillation
        FROM activities
        ORDER BY start_time DESC LIMIT 30
    """).fetchall()
    db.close()

    recent_str = ''
    for r in recent:
        type_cn = {'running': '跑步', 'strength_training': '力量', 'cycling': '骑行', 'lap_swimming': '游泳'}.get(r['type'], r['type'] or '其他')
        dist_str = f'{r["distance"]/1000:.1f}km' if r['distance'] else '-'
        pace_str = _format_pace_str(r['avg_pace']) if r['type'] == 'running' else '-'
        hr_str = f'{round(r["avg_heart_rate"])}bpm' if r['avg_heart_rate'] else '-'
        extras = []
        if r.get('avg_cadence'): extras.append(f'步频{round(r["avg_cadence"])}')
        if r.get('avg_ground_contact_time'): extras.append(f'触地{round(r["avg_ground_contact_time"])}ms')
        if r.get('avg_vertical_oscillation'): extras.append(f'振幅{r["avg_vertical_oscillation"]/10:.1f}cm')
        extra_str = f' [{", ".join(extras)}]' if extras else ''
        recent_str += f"  {r['start_time'][:10]} {type_cn} {r['name']}: {dist_str} @{pace_str} 心率{hr_str}{extra_str}\n"

    summary = f"最近12周: {row['count']}次跑步, 总跑量{row['total_distance']/1000:.1f}km, 平均配速{_format_pace_str(row['avg_pace'])}, 平均心率{row['avg_hr']:.0f}, 最近一次: {row['last_run'] or '无'}"
    return summary, recent_str


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
        if h.get('hrv_avg'): parts.append(f"HRV={round(h['hrv_avg'])}ms")
        if h.get('sleep_score'): parts.append(f"睡眠={h['sleep_score']}分")
        if h.get('sleep_duration'): parts.append(f"{h['sleep_duration']}h")
        if h.get('resting_hr'): parts.append(f"静息HR={round(h['resting_hr'])}")
        if h.get('avg_stress'): parts.append(f"压力={round(h['avg_stress'])}")
        if h.get('body_battery_max'): parts.append(f"电量={h['body_battery_max']}/{h.get('body_battery_min','-')}")
        lines.append('  ' + ' | '.join(parts))
    return '\n'.join(lines)


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

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.route('/api/sync', methods=['POST'])
    def sync():
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': '需要邮箱和密码'}), 400

        result = sync_service.sync(data['email'], data['password'])
        if 'error' in result:
            return jsonify(result), 401
        return jsonify(result)

    @app.route('/api/sync/backfill', methods=['POST'])
    def backfill_details():
        """Backfill running dynamics for existing activities without detail data."""
        from backend.garmin_client import GarminClient

        data = request.get_json() or {}
        limit = int(data.get('limit', 50))
        db = get_db()
        rows = db.execute(
            "SELECT id FROM activities WHERE detail_json IS NULL AND type='running' ORDER BY start_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
        db.close()

        if not rows:
            return jsonify({'status': 'ok', 'filled': 0, 'message': '所有活动已有详情数据'})

        gc = GarminClient()
        login = gc.login('', '')  # rely on saved tokens
        if not login.get('success'):
            return jsonify({'error': '需要先同步登录一次以保存 Token'}), 401

        filled = 0
        for row in rows:
            try:
                detail = gc.fetch_activity_details(row['id'])
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
        days = int(request.args.get('days', 14))
        db = get_db()
        rows = db.execute(
            "SELECT * FROM health_data ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        db.close()
        return jsonify([dict(r) for r in reversed(rows)])

    @app.route('/api/activities')
    def list_activities():
        activity_type = request.args.get('type')
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        search = request.args.get('q')

        db = get_db()
        query = "SELECT * FROM activities WHERE 1=1"
        params = []

        if activity_type:
            query += " AND type=?"
            params.append(activity_type)
        if date_from:
            query += " AND start_time >= ?"
            params.append(date_from)
        if date_to:
            query += " AND start_time <= ?"
            params.append(date_to)
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

        result = {'vdot': best_vdot, 'source': best_source, 'predictions': {}, 'pace_zones': {}, 'hr_zones': {}}

        if best_vdot > 0:
            vmax = _calc_v_from_vo2(best_vdot)
            for dist_name, dist_m in RACE_DISTANCES.items():
                result['predictions'][dist_name] = predict_time_str(best_vdot, dist_m)

            if vmax > 0:
                bp = 1000 / vmax * 60
                for name, (lo, hi) in TRAINING_PACES.items():
                    result['pace_zones'][name] = {
                        'fast': _sec_to_pace(bp / hi),
                        'slow': _sec_to_pace(bp / lo)
                    }

            if best_5k:
                result['best_5k'] = f"{best_5k['name']} ({best_5k['duration']/60:.1f}min)"

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

        pace_dist = db.execute("""
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
                COUNT(*) as count
            FROM activities
            WHERE type='running' AND avg_pace > 0
              AND start_time >= ? AND start_time <= ?
            GROUP BY pace_range
            ORDER BY MIN(avg_pace)
        """, (date_from, date_to)).fetchall()

        db.close()

        return jsonify({
            'overview': dict(overview),
            'monthly': [dict(r) for r in reversed(monthly)],
            'pace_distribution': [dict(r) for r in pace_dist],
        })

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
        summary, recent_activities = _get_training_summary()
        health_summary = _get_health_summary()
        recent = chat_service.get_history(session_id=session_id) if session_id else []
        profile_info = _get_profile_info()
        messages = chat_service.build_messages(session_id, question, summary + health_summary, recent,
                                                recent_activities, profile_info)

        llm = _get_llm_client()

        def generate():
            full_answer = ''
            try:
                for chunk in llm.chat_stream(messages):
                    full_answer += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                chat_service.save_message(session_id, 'user', question, summary)
                chat_service.save_message(session_id, 'assistant', full_answer, summary)
            except Exception as e:
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
        date_to = data.get('to', '2099-12-31')

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
                best_5k_time = f"{best_5k['name']} ({best_5k['duration']/60:.1f}min, {best_5k['start_time'][:10]})"

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
                   training_effect, vo2max
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
        training_data['date_range'] = f'{date_from} ~ {date_to}'
        training_data['performances'] = performances
        training_data['profile'] = profile
        training_data['recent'] = recent_str
        training_data['activities'] = individual_activities
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
                        _save_report(task_id, date_from, date_to, update['report'])
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
