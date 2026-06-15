import pytest
from unittest.mock import patch, MagicMock
from backend.garmin_client import (
    GarminClient, _patch_for_cn, _restore_patches, _get_gc_client,
)


@patch('backend.garmin_client.Garmin')
def test_login_success(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin_class.return_value = mock_garmin
    mock_garmin.login.return_value = None

    client = GarminClient()
    result = client.login('test@example.com', 'password')

    assert result['success'] is True
    assert mock_garmin_class.called
    args, kwargs = mock_garmin_class.call_args
    assert args[0] == 'test@example.com'
    assert args[1] == 'password'
    assert kwargs.get('is_cn') is True


@patch('backend.garmin_client.Garmin')
def test_login_success_with_tokenstore(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin_class.return_value = mock_garmin
    mock_garmin.login.return_value = None

    client = GarminClient(tokenstore='/tmp/test_tokens')
    result = client.login('test@example.com', 'password')

    assert result['success'] is True
    args, kwargs = mock_garmin.login.call_args
    assert 'tokenstore' in kwargs
    assert 'test_tokens' in kwargs['tokenstore']


@patch('backend.garmin_client.Garmin')
def test_login_needs_captcha(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin_class.return_value = mock_garmin
    mock_garmin.login.side_effect = Exception("验证码")

    client = GarminClient()
    result = client.login('test@example.com', 'password')
    assert 'error' in result or result['success'] is False


def test_monkey_patch_restore():
    gc = _get_gc_client()
    orig_mobile_cffi = gc.Client._mobile_login_cffi
    orig_establish = gc.Client._establish_session

    _patch_for_cn()
    assert gc.Client._mobile_login_cffi is not orig_mobile_cffi
    assert gc.Client._establish_session is not orig_establish

    _restore_patches()
    assert gc.Client._mobile_login_cffi is orig_mobile_cffi
    assert gc.Client._establish_session is orig_establish


@patch('backend.garmin_client.Garmin')
def test_fetch_activities(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin.get_activities.return_value = [
        {
            'activityId': 123,
            'activityName': 'Morning Run',
            'activityType': {'typeKey': 'running'},
            'startTimeLocal': '2026-05-01 07:00:00',
            'duration': 1800.0,
            'distance': 5000.0,
            'averageHR': 145.0,
            'maxHR': 170.0,
            'elevationGain': 50.0,
        }
    ]

    client = GarminClient()
    client.client = mock_garmin
    activities = client.fetch_activities(limit=10)

    assert len(activities) == 1
    assert activities[0]['id'] == 123
    assert activities[0]['type'] == 'running'
    assert activities[0]['distance'] == 5000.0


@patch('backend.garmin_client.Garmin')
def test_fetch_activity_splits(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin.get_activity_splits.return_value = [
        {'distance': 1000.0, 'duration': 360.0}
    ]

    client = GarminClient()
    client.client = mock_garmin
    splits = client.fetch_activity_splits(123)

    assert len(splits) == 1
    assert splits[0]['distance'] == 1000.0
