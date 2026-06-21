from backend.report_generator import calc_vdot, _calc_v_from_vo2, _sec_to_pace


TRAINING_PACE_DEFS = [
    ('轻松跑 E', (0.72, 0.82)),
    ('马拉松配速 M', (0.82, 0.90)),
    ('乳酸阈值 T', (0.90, 0.96)),
    ('间歇跑 I', (0.96, 1.02)),
    ('重复跑 R', (1.02, 1.10)),
]


def get_best_vdot(db):
    rows = db.execute("""
        SELECT distance, duration
        FROM activities
        WHERE type='running' AND distance >= 5000 AND duration > 0
    """).fetchall()
    best_vdot = 0
    for row in rows:
        if row['distance'] and row['duration']:
            pace = row['duration'] / (row['distance'] / 1000)
            if pace <= 600:
                best_vdot = max(best_vdot, calc_vdot(row['distance'], row['duration']))
    return best_vdot


def build_zone_defs(vdot):
    if not vdot or vdot <= 0:
        return []
    vmax = _calc_v_from_vo2(vdot)
    if vmax <= 0:
        return []

    base_pace = 1000 / vmax * 60
    zone_defs = []
    for name, (lo, hi) in TRAINING_PACE_DEFS:
        fast = base_pace / hi
        slow = base_pace / lo
        zone_defs.append({
            'pace_range': f'{name} {_sec_to_pace(fast)}-{_sec_to_pace(slow)}',
            'count': 0,
            'fast': fast,
            'slow': slow,
        })
    return zone_defs


def get_pace_distribution(db, date_from, date_to):
    """Return the same pace distribution used by dashboard and reports.

    Distances are aggregated by Daniels E/M/T/I/R zones when VDOT is available.
    Activity splits are preferred when they cover the activity distance well,
    otherwise whole-activity average pace is used.
    """
    best_vdot = get_best_vdot(db)
    zone_defs = build_zone_defs(best_vdot)
    if not zone_defs:
        return _fallback_distribution(db, date_from, date_to)

    pace_rows = db.execute("""
        SELECT id, avg_pace, distance, duration
        FROM activities
        WHERE type='running' AND avg_pace > 0
          AND start_time >= ? AND start_time <= ?
        ORDER BY avg_pace
    """, (date_from, date_to)).fetchall()

    def add_zone_distance(pace, distance):
        distance_km = (distance or 0) / 1000
        if not pace or distance_km <= 0:
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

    return [
        {'pace_range': z['pace_range'], 'count': round(z['count'], 2)}
        for z in zone_defs
    ]


def _fallback_distribution(db, date_from, date_to):
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
    return [dict(r) for r in rows]
