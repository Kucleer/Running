import ast
import json


RUNNING_ACTIVITY_TYPES = {'running', 'track_running', 'treadmill_running', 'indoor_running'}


def is_running_activity_type(activity_type):
    return activity_type in RUNNING_ACTIVITY_TYPES


def pace_seconds(distance_m, duration_s):
    if not distance_m or not duration_s:
        return None
    km = distance_m / 1000
    if km <= 0:
        return None
    return duration_s / km


def format_pace(seconds):
    if not seconds:
        return '-'
    minutes = int(seconds // 60)
    sec = int(round(seconds % 60))
    if sec == 60:
        minutes += 1
        sec = 0
    return f'{minutes}:{sec:02d}/km'


def normalize_official_splits(raw, source='garmin'):
    splits = _extract_split_items(raw)
    result = []
    for idx, item in enumerate(splits, start=1):
        if not isinstance(item, dict):
            continue
        distance = _first_number(item, [
            'distance', 'maxDistanceWithPrecision', 'maxDistance', 'totalDistance',
            'splitDistance', 'sumDistance'
        ])
        duration = _first_number(item, [
            'duration', 'movingDuration', 'elapsedDuration', 'timerDuration',
            'totalTimerTime', 'sumDuration'
        ])
        if not distance or not duration:
            continue
        result.append({
            'split_index': idx,
            'source': source,
            'split_type': item.get('splitType') or item.get('type') or item.get('splitTypeKey'),
            'distance': distance,
            'duration': duration,
            'moving_duration': _first_number(item, ['movingDuration', 'sumMovingDuration']),
            'avg_pace': pace_seconds(distance, duration),
            'avg_heart_rate': _first_number(item, ['averageHR', 'avgHr', 'averageHeartRate']),
            'max_heart_rate': _first_number(item, ['maxHR', 'maxHr', 'maxHeartRate']),
            'avg_cadence': _first_number(item, ['averageRunCadence', 'avgRunCadence', 'avgStepFrequency']),
            'avg_power': _first_number(item, ['averagePower', 'avgPower', 'normalizedPower']),
            'elevation_gain': _first_number(item, ['elevationGain', 'totalAscent']),
            'raw_json': json.dumps(item, ensure_ascii=False),
        })
    return result


def is_meaningful_split(split):
    distance = split.get('distance') or 0
    duration = split.get('duration') or 0
    split_type = str(split.get('split_type') or '').upper()
    if 200 <= distance <= 5000:
        return True
    if duration >= 20 and distance < 200 and any(k in split_type for k in ['REST', 'RECOVERY', 'INACTIVE']):
        return True
    return False


def splits_from_detail_json(detail_json):
    detail = parse_detail_json(detail_json)
    if not detail:
        return []

    official = normalize_official_splits(
        detail.get('summary', {}).get('splitSummaries'),
        source='detail_split_summary'
    )
    useful = [s for s in official if 200 <= (s.get('distance') or 0) <= 5000]
    if useful:
        return useful

    return calculate_km_splits_from_detail(detail)


def calculate_km_splits_from_detail(detail, segment_m=1000):
    metrics = detail.get('metrics', {}) if isinstance(detail, dict) else {}
    descriptors = metrics.get('metricDescriptors') or []
    rows = metrics.get('activityDetailMetrics') or []
    index = {d.get('key'): d.get('metricsIndex') for d in descriptors if isinstance(d, dict)}
    dist_i = index.get('sumDistance')
    dur_i = index.get('sumDuration')
    if dur_i is None:
        dur_i = index.get('sumElapsedDuration')
    hr_i = index.get('directHeartRate')
    cad_i = index.get('directDoubleCadence')
    if cad_i is None:
        cad_i = index.get('directRunCadence')
    power_i = index.get('directPower')
    elev_i = index.get('directElevation')
    if dist_i is None or dur_i is None:
        return []

    points = []
    for row in rows:
        values = row.get('metrics') if isinstance(row, dict) else None
        if not isinstance(values, list):
            continue
        dist = _value_at(values, dist_i)
        dur = _value_at(values, dur_i)
        if dist is None or dur is None:
            continue
        points.append({
            'distance': float(dist),
            'duration': float(dur),
            'hr': _value_at(values, hr_i),
            'cadence': _value_at(values, cad_i),
            'power': _value_at(values, power_i),
            'elevation': _value_at(values, elev_i),
        })

    points.sort(key=lambda p: p['distance'])
    if len(points) < 2:
        return []

    total_distance = points[-1]['distance']
    splits = []
    start = points[0]
    start_distance = start['distance']
    target = start_distance + segment_m
    split_index = 1

    while target <= total_distance + 1:
        end = _interpolate_point(points, target)
        if not end:
            break
        split = _build_metric_split(split_index, start, end, points, target - segment_m, target)
        if split:
            splits.append(split)
        start = end
        split_index += 1
        target += segment_m

    if total_distance - start['distance'] >= 200:
        split = _build_metric_split(split_index, start, points[-1], points, start['distance'], total_distance)
        if split:
            splits.append(split)

    return splits


def save_splits(db, activity_id, splits):
    db.execute("DELETE FROM activity_splits WHERE activity_id=?", (activity_id,))
    for split in splits:
        db.execute("""
            INSERT OR REPLACE INTO activity_splits
            (activity_id, split_index, source, split_type, distance, duration, moving_duration,
             avg_pace, avg_heart_rate, max_heart_rate, avg_cadence, avg_power, elevation_gain, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            activity_id,
            split.get('split_index'),
            split.get('source'),
            split.get('split_type'),
            split.get('distance'),
            split.get('duration'),
            split.get('moving_duration'),
            split.get('avg_pace'),
            split.get('avg_heart_rate'),
            split.get('max_heart_rate'),
            split.get('avg_cadence'),
            split.get('avg_power'),
            split.get('elevation_gain'),
            split.get('raw_json'),
        ))


def get_activity_splits(db, activity_id):
    rows = db.execute(
        "SELECT * FROM activity_splits WHERE activity_id=? ORDER BY split_index",
        (activity_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def build_split_summary(activity, splits, max_splits=12):
    if not splits:
        return ''
    rows = [s for s in splits if s.get('distance') and s.get('duration')]
    if not rows:
        return ''

    total_distance = sum(s.get('distance') or 0 for s in rows)
    total_duration = sum(s.get('duration') or 0 for s in rows)
    avg_pace = pace_seconds(total_distance, total_duration)
    fastest = min(rows, key=lambda s: s.get('avg_pace') or 99999)
    slowest = max(rows, key=lambda s: s.get('avg_pace') or 0)
    half = max(1, len(rows) // 2)
    first = rows[:half]
    second = rows[half:] or rows[half - 1:]
    first_pace = pace_seconds(sum(s.get('distance') or 0 for s in first), sum(s.get('duration') or 0 for s in first))
    second_pace = pace_seconds(sum(s.get('distance') or 0 for s in second), sum(s.get('duration') or 0 for s in second))
    first_hr = _avg([s.get('avg_heart_rate') for s in first])
    second_hr = _avg([s.get('avg_heart_rate') for s in second])
    lines = [
        f"{activity.get('start_time', '')[:10]} {activity.get('name', '')}: "
        f"{total_distance/1000:.1f}km, 均配{format_pace(avg_pace)}, "
        f"最快第{fastest.get('split_index')}段{format_pace(fastest.get('avg_pace'))}, "
        f"最慢第{slowest.get('split_index')}段{format_pace(slowest.get('avg_pace'))}"
    ]
    if first_pace and second_pace:
        diff = second_pace - first_pace
        trend = '后半程变慢' if diff > 5 else '后半程变快' if diff < -5 else '前后半程稳定'
        lines.append(f"  趋势: {trend} {abs(diff):.0f}s/km；前半{format_pace(first_pace)}，后半{format_pace(second_pace)}")
    if first_hr and second_hr:
        lines.append(f"  心率漂移: 前半{first_hr:.0f}bpm，后半{second_hr:.0f}bpm，变化{second_hr-first_hr:+.0f}bpm")
    interval_summary = detect_interval_pattern(rows)
    if interval_summary:
        lines.append(f"  间歇识别: {interval_summary}")
    detail = []
    for s in rows[:max_splits]:
        hr = f", HR {s['avg_heart_rate']:.0f}" if s.get('avg_heart_rate') else ''
        detail.append(f"{int(s.get('split_index') or 0)}:{format_pace(s.get('avg_pace'))}{hr}")
    if detail:
        suffix = ' ...' if len(rows) > max_splits else ''
        lines.append(f"  分段: {'; '.join(detail)}{suffix}")
    return '\n'.join(lines)


def detect_interval_pattern(splits):
    rows = [s for s in splits if s.get('duration')]
    if len(rows) < 3:
        return ''
    rest_rows = [
        s for s in rows
        if (s.get('distance') or 0) < 200
        or 'REST' in str(s.get('split_type') or '').upper()
        or 'RECOVERY' in str(s.get('split_type') or '').upper()
    ]
    pace_rows = [s for s in rows if s.get('avg_pace') and (s.get('distance') or 0) >= 200]
    if len(pace_rows) < 3:
        if rest_rows:
            return f"发现{len(rest_rows)}个休息/恢复段，疑似跑-休-跑结构"
        return ''
    paces = sorted(float(s['avg_pace']) for s in pace_rows)
    median = _median(paces)
    if median <= 0:
        return ''
    fast = [s for s in pace_rows if s.get('avg_pace') and s['avg_pace'] <= median * 0.90]
    slow = [s for s in pace_rows if s.get('avg_pace') and s['avg_pace'] >= median * 1.15]
    avg = sum(paces) / len(paces)
    variance = sum((p - avg) ** 2 for p in paces) / len(paces)
    cv = (variance ** 0.5) / avg if avg else 0
    alternating = _count_pace_transitions(pace_rows, median) >= 2
    if rest_rows:
        return f"发现{len(rest_rows)}个休息/恢复段，快段{len(fast)}个、慢段{len(slow)}个，疑似间歇训练"
    if len(fast) >= 2 and len(slow) >= 2 and (alternating or cv >= 0.12):
        return f"未发现显式休息段，但配速呈快慢交替，快段{len(fast)}个、慢段{len(slow)}个，疑似间歇或法特莱克"
    return ''


def _count_pace_transitions(rows, median):
    labels = []
    for row in rows:
        pace = row.get('avg_pace')
        if not pace:
            continue
        if pace <= median * 0.92:
            labels.append('fast')
        elif pace >= median * 1.10:
            labels.append('slow')
        else:
            labels.append('steady')
    compact = []
    for label in labels:
        if label == 'steady':
            continue
        if not compact or compact[-1] != label:
            compact.append(label)
    return max(0, len(compact) - 1)


def _median(values):
    if not values:
        return 0
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def parse_detail_json(detail_json):
    if not detail_json:
        return None
    if isinstance(detail_json, dict):
        return detail_json
    try:
        return json.loads(detail_json)
    except Exception:
        try:
            return ast.literal_eval(detail_json)
        except Exception:
            return None


def _extract_split_items(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ['splitSummaries', 'splits', 'lapDTOs', 'activitySplits', 'splitDTOs']:
            value = raw.get(key)
            if isinstance(value, list):
                return value
        return [raw]
    return []


def _first_number(data, keys):
    for key in keys:
        value = data.get(key) if isinstance(data, dict) else None
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _value_at(values, index):
    if index is None:
        return None
    try:
        value = values[int(index)]
    except (IndexError, TypeError, ValueError):
        return None
    return value if value is not None else None


def _interpolate_point(points, target_distance):
    prev = points[0]
    for point in points[1:]:
        if point['distance'] >= target_distance:
            span = point['distance'] - prev['distance']
            ratio = 0 if span <= 0 else (target_distance - prev['distance']) / span
            result = {'distance': target_distance}
            for key in ['duration', 'hr', 'cadence', 'power', 'elevation']:
                a = prev.get(key)
                b = point.get(key)
                result[key] = _interp(a, b, ratio)
            return result
        prev = point
    return None


def _build_metric_split(split_index, start, end, points, from_distance, to_distance):
    distance = end['distance'] - start['distance']
    duration = end['duration'] - start['duration']
    if distance <= 0 or duration <= 0:
        return None
    segment_points = [p for p in points if from_distance <= p['distance'] <= to_distance]
    avg_hr = _avg([p.get('hr') for p in segment_points])
    max_hr = _max([p.get('hr') for p in segment_points])
    avg_cadence = _avg([p.get('cadence') for p in segment_points])
    avg_power = _avg([p.get('power') for p in segment_points])
    elevation_gain = None
    if start.get('elevation') is not None and end.get('elevation') is not None:
        elevation_gain = max(0, end['elevation'] - start['elevation'])
    return {
        'split_index': split_index,
        'source': 'computed_1km',
        'split_type': '1km',
        'distance': distance,
        'duration': duration,
        'moving_duration': duration,
        'avg_pace': pace_seconds(distance, duration),
        'avg_heart_rate': avg_hr,
        'max_heart_rate': max_hr,
        'avg_cadence': avg_cadence,
        'avg_power': avg_power,
        'elevation_gain': elevation_gain,
        'raw_json': None,
    }


def _interp(a, b, ratio):
    if a is None:
        return b
    if b is None:
        return a
    return float(a) + (float(b) - float(a)) * ratio


def _avg(values):
    nums = [float(v) for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


def _max(values):
    nums = [float(v) for v in values if v is not None]
    return max(nums) if nums else None
