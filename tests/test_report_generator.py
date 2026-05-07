import pytest
from unittest.mock import patch, MagicMock
from backend.report_generator import (
    ReportGenerator, calc_vdot, predict_time, predict_time_str, _calc_vo2, _calc_v_from_vo2
)


def test_vdot_calculation():
    # 5K in 27:00 → VDOT ~33 (user confirmed ~33.2)
    vdot = calc_vdot(5000, 27 * 60)
    assert 32.0 <= vdot <= 35.0

    # 5K in 24:30 → VDOT ~37
    vdot = calc_vdot(5000, 24.5 * 60)
    assert 35.0 <= vdot <= 40.0

    # 5K in 20:00 → VDOT ~48
    vdot = calc_vdot(5000, 20 * 60)
    assert 46 <= vdot <= 51


def test_vdot_race_prediction():
    vdot = calc_vdot(5000, 27 * 60)
    assert 32.0 <= vdot <= 35.0

    # Higher VDOT → faster 10K
    t_low = predict_time(33.0, 10000)
    t_high = predict_time(37.3, 10000)
    assert t_low is not None
    assert t_high is not None
    assert t_high < t_low

    # Same VDOT → different paces for different distances
    t_5k = predict_time(33.0, 5000)
    t_10k = predict_time(33.0, 10000)
    pace_5k = t_5k * 60 / 5
    pace_10k = t_10k * 60 / 10
    assert pace_10k > pace_5k, f"10K pace ({pace_10k:.0f}s/km) should be slower than 5K ({pace_5k:.0f}s/km)"

    # Marathon > 3 hours for VDOT ~33
    ts = predict_time_str(33.0, 42195)
    assert ':' in ts
    parts = ts.split(':')
    assert len(parts) >= 2
    if len(parts) == 3:
        assert int(parts[0]) >= 2  # marathon > 2 hours


def test_vdot_zero_edge():
    assert calc_vdot(0, 100) == 0
    assert calc_vdot(5000, 0) == 0
    assert predict_time(0, 10000) is None
    assert predict_time_str(0, 10000) == 'N/A'


def test_data_context_includes_vdot():
    data = {
        'total_runs': 20, 'total_distance': 150000, 'total_duration': 36000,
        'avg_pace': 330, 'avg_hr': 145, 'total_elevation': 500,
        'has_strength': False, 'date_range': '2026-01-01 ~ 2026-05-01',
        'performances': {'vdot': 33.2, 'source': 'Test 5K (5.0km, 27.0min)', 'best_5k': 'Test Run'},
        'profile': {'age': '28', 'gender': 'male', 'weight': '65', 'resting_hr': '55', 'max_hr': '190'},
        'recent': '2026-05-01 Run: 5.0km @330s/km',
        'activities': [
            {'name': 'Morning Run', 'type': 'running', 'distance': 5000, 'duration': 1650,
             'avg_pace': 330, 'avg_heart_rate': 145, 'max_heart_rate': 170,
             'elevation_gain': 50, 'start_time': '2026-05-01 07:00:00'},
            {'name': 'Strength Workout', 'type': 'strength_training', 'distance': 0,
             'duration': 2700, 'avg_pace': None, 'avg_heart_rate': 120,
             'max_heart_rate': 145, 'elevation_gain': 0, 'start_time': '2026-05-02 18:00:00'},
        ]
    }
    gen = ReportGenerator('url', 'key', 'model')
    ctx = gen._build_data_context(data)
    assert '33.2' in ctx
    assert 'VDOT' in ctx
    assert '5K' in ctx
    assert '10K' in ctx
    assert '轻松跑' in ctx
    assert '65 kg' in ctx
    assert 'Morning Run' in ctx
    assert 'Strength Workout' in ctx
    assert '5.00km' in ctx
    assert '近期训练记录明细' in ctx
    # Verify pace table output format
    assert '/km' in ctx
    assert '~' in ctx


@patch('backend.report_generator.LLMClient')
def test_report_generation_flow(mock_llm_class):
    mock_llm = MagicMock()
    mock_llm_class.return_value = mock_llm
    mock_llm.chat.side_effect = [
        '数据分析师首轮分析...',
        '分析师回复...',
        '教练回复...',
        '分析师回复2...',
        '教练回复2...',
        '主教练整合报告...',
    ]

    generator = ReportGenerator(
        base_url='http://fake',
        api_key='test',
        model='test-model',
        rounds=3
    )

    training_data = {
        'total_runs': 20,
        'total_distance': 150000,
        'avg_pace': 330,
        'has_strength': False
    }

    report = generator.generate(training_data)
    assert report is not None
    assert '主教练整合报告' in report
    assert mock_llm.chat.call_count >= 5


@patch('backend.report_generator.LLMClient')
def test_report_with_strength_data(mock_llm_class):
    mock_llm = MagicMock()
    mock_llm_class.return_value = mock_llm
    mock_llm.chat.side_effect = [
        'analyst', 'coach', 'strength', 'analyst', 'coach', 'strength',
        'analyst', 'coach', 'strength', 'summarizer'
    ]

    generator = ReportGenerator('url', 'key', 'model', rounds=3)
    generator.generate({'total_runs': 10, 'has_strength': True})

    assert mock_llm.chat.call_count >= 6


def test_report_generator_handles_llm_error():
    generator = ReportGenerator('url', 'key', 'model', rounds=3)
    with patch('backend.report_generator.LLMClient') as mock_cls:
        mock_llm = MagicMock()
        mock_cls.return_value = mock_llm
        mock_llm.chat.side_effect = Exception('API 超时')

        with pytest.raises(Exception):
            generator.generate({'total_runs': 5})
