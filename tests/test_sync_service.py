import pytest
from unittest.mock import patch, MagicMock
from backend.database import init_db, get_db, set_db_path
from backend.sync_service import SyncService


@pytest.fixture
def sync_service(test_db_path):
    from backend.database import set_db_path, init_db
    set_db_path(test_db_path)
    init_db()
    return SyncService()


@patch('backend.sync_service.GarminClient')
def test_sync_new_activities(mock_garmin_class, sync_service):
    mock_client = MagicMock()
    mock_garmin_class.return_value = mock_client
    mock_client.login.return_value = {'success': True}
    mock_client.fetch_activities.return_value = [
        {
            'id': 1, 'name': 'Run 1', 'type': 'running',
            'start_time': '2026-05-01 07:00:00', 'duration': 1800.0,
            'distance': 5000.0, 'avg_heart_rate': 145.0,
            'max_heart_rate': 170.0, 'avg_pace': 360.0,
            'elevation_gain': 50.0, 'raw_json': '{"test": true}'
        }
    ]
    mock_client.fetch_activity_details.return_value = None

    result = sync_service.sync(email='test@test.com', password='pw')

    assert result['new_count'] == 1
    assert result['total_checked'] == 1

    db = get_db()
    row = db.execute("SELECT * FROM activities WHERE id=1").fetchone()
    db.close()
    assert row is not None
    assert row['name'] == 'Run 1'


def test_sync_skips_existing(sync_service):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time)
        VALUES (1, 'Existing', 'running', '2026-01-01')
    """)
    db.commit()
    db.close()

    with patch('backend.sync_service.GarminClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.login.return_value = {'success': True}
        mock_client.fetch_activities.return_value = [
            {'id': 1, 'name': 'Existing Updated', 'type': 'running',
             'start_time': '2026-01-01', 'duration': 0, 'distance': 0,
             'avg_heart_rate': None, 'max_heart_rate': None,
             'avg_pace': None, 'elevation_gain': 0, 'raw_json': '{}'}
        ]

        result = sync_service.sync(email='test@test.com', password='pw')
        assert result['new_count'] == 0
