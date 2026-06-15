from backend.splits import (
    build_split_summary,
    calculate_km_splits_from_detail,
    detect_interval_pattern,
    normalize_official_splits,
)


def test_normalize_official_splits():
    raw = [
        {'distance': 1000, 'duration': 300, 'averageHR': 150, 'splitType': 'KM'},
        {'distance': 1000, 'duration': 330, 'averageHR': 155, 'splitType': 'KM'},
    ]

    splits = normalize_official_splits(raw, source='garmin')

    assert len(splits) == 2
    assert splits[0]['split_index'] == 1
    assert splits[0]['avg_pace'] == 300
    assert splits[1]['avg_heart_rate'] == 155


def test_calculate_km_splits_from_detail_metrics():
    detail = {
        'metrics': {
            'metricDescriptors': [
                {'metricsIndex': 0, 'key': 'sumDuration'},
                {'metricsIndex': 1, 'key': 'sumDistance'},
                {'metricsIndex': 2, 'key': 'directHeartRate'},
                {'metricsIndex': 3, 'key': 'directRunCadence'},
                {'metricsIndex': 4, 'key': 'directPower'},
            ],
            'activityDetailMetrics': [
                {'metrics': [0, 0, 120, 170, 200]},
                {'metrics': [300, 1000, 150, 180, 220]},
                {'metrics': [620, 2000, 160, 182, 230]},
            ],
        }
    }

    splits = calculate_km_splits_from_detail(detail)

    assert len(splits) == 2
    assert splits[0]['distance'] == 1000
    assert splits[0]['duration'] == 300
    assert splits[1]['duration'] == 320
    assert splits[1]['avg_pace'] == 320


def test_build_split_summary():
    activity = {'name': 'Morning Run', 'start_time': '2026-06-13 07:00:00'}
    splits = [
        {'split_index': 1, 'distance': 1000, 'duration': 300, 'avg_pace': 300, 'avg_heart_rate': 145},
        {'split_index': 2, 'distance': 1000, 'duration': 330, 'avg_pace': 330, 'avg_heart_rate': 155},
    ]

    summary = build_split_summary(activity, splits)

    assert 'Morning Run' in summary
    assert '最快第1段' in summary
    assert '心率漂移' in summary


def test_detect_interval_pattern_from_fast_slow_splits():
    splits = [
        {'split_index': 1, 'distance': 1000, 'duration': 240, 'avg_pace': 240},
        {'split_index': 2, 'distance': 1000, 'duration': 420, 'avg_pace': 420},
        {'split_index': 3, 'distance': 1000, 'duration': 245, 'avg_pace': 245},
        {'split_index': 4, 'distance': 1000, 'duration': 430, 'avg_pace': 430},
    ]

    assert '疑似' in detect_interval_pattern(splits)
