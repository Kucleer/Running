from unittest.mock import patch, MagicMock
from backend.database import get_db


def test_app_health_check(client):
    resp = client.get('/api/ping')
    assert resp.status_code == 200
    assert resp.json['status'] == 'ok'


def test_app_serves_frontend(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'<!DOCTYPE html>' in resp.data


def test_sync_endpoint(client):
    import backend.app as app_module
    original = app_module.sync_service.sync
    app_module.sync_service.sync = MagicMock(return_value={'new_count': 5, 'total_checked': 10})

    resp = client.post('/api/sync', json={
        'email': 'test@test.com',
        'password': 'test123'
    })
    assert resp.status_code == 200
    assert resp.json['new_count'] == 5

    app_module.sync_service.sync = original


def test_sync_requires_credentials(client):
    resp = client.post('/api/sync', json={})
    assert resp.status_code == 400


def test_activities_list(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance)
        VALUES (1, 'Run 1', 'running', '2026-05-01 07:00:00', 1800, 5000)
    """)
    db.commit()
    db.close()

    resp = client.get('/api/activities')
    assert resp.status_code == 200
    data = resp.json
    assert len(data) == 1
    assert data[0]['name'] == 'Run 1'


def test_activities_filter_by_type(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance)
        VALUES (2, 'Strength', 'strength_training', '2026-05-02', 3600, 0)
    """)
    db.commit()
    db.close()

    resp = client.get('/api/activities?type=running')
    data = resp.json
    assert all(a['type'] == 'running' for a in data)


def test_activities_running_filter_includes_running_family_and_full_day(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance)
        VALUES
        (21, 'Track Run', 'track_running', '2026-06-13 06:30:00', 1800, 5000),
        (22, 'Treadmill Run', 'treadmill_running', '2026-06-13 20:30:00', 1800, 5000),
        (23, 'Bike', 'cycling', '2026-06-13 09:00:00', 1800, 10000)
    """)
    db.commit()
    db.close()

    resp = client.get('/api/activities?type=running&from=2026-06-13&to=2026-06-13')
    assert resp.status_code == 200
    types = {a['type'] for a in resp.json}
    assert 'track_running' in types
    assert 'treadmill_running' in types
    assert 'cycling' not in types


def test_activity_detail(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance,
            avg_heart_rate, max_heart_rate, avg_pace, elevation_gain, raw_json)
        VALUES (10, 'Detail Run', 'running', '2026-05-03', 3600, 10000, 150, 175, 360, 100, '{}')
    """)
    db.commit()
    db.close()

    resp = client.get('/api/activity/10')
    assert resp.status_code == 200
    assert resp.json['name'] == 'Detail Run'
    assert resp.json['distance'] == 10000


def test_activity_not_found(client):
    resp = client.get('/api/activity/99999')
    assert resp.status_code == 404


def test_activity_splits_endpoint(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance)
        VALUES (11, 'Split Run', 'running', '2026-05-04', 720, 2000)
    """)
    db.execute("""
        INSERT INTO activity_splits
        (activity_id, split_index, source, split_type, distance, duration, avg_pace, avg_heart_rate)
        VALUES
        (11, 1, 'garmin', 'KM', 1000, 360, 360, 140),
        (11, 2, 'garmin', 'KM', 1000, 355, 355, 145)
    """)
    db.commit()
    db.close()

    resp = client.get('/api/activities/11/splits')
    assert resp.status_code == 200
    assert len(resp.json) == 2
    assert resp.json[0]['avg_pace'] == 360


def test_stats_endpoint(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance, avg_heart_rate)
        VALUES
        (101, 'Run May', 'running', '2026-05-01 07:00:00', 1800, 5000, 145),
        (102, 'Run May2', 'running', '2026-05-03 08:00:00', 2400, 7000, 150),
        (103, 'Run Apr', 'running', '2026-04-15 06:00:00', 3600, 10000, 140)
    """)
    db.commit()
    db.close()

    resp = client.get('/api/stats?period=monthly')
    assert resp.status_code == 200
    data = resp.json
    assert 'overview' in data
    assert 'monthly' in data
    assert round(sum(p['count'] for p in data['pace_distribution']), 1) == 22.0


def test_report_list_empty(client):
    resp = client.get('/api/reports')
    assert resp.status_code == 200
    assert resp.json == []


def test_report_list_and_get(client):
    db = get_db()
    db.execute(
        "INSERT INTO reports (title, date_from, date_to, content) VALUES (?, ?, ?, ?)",
        ('测试报告', '2026-01-01', '2026-06-01', '# 测试\n内容')
    )
    db.commit()
    db.close()

    resp = client.get('/api/reports')
    assert resp.status_code == 200
    assert len(resp.json) == 1
    assert resp.json[0]['title'] == '测试报告'
    report_id = resp.json[0]['id']

    resp = client.get(f'/api/report/{report_id}')
    assert resp.status_code == 200
    data = resp.json
    assert data['title'] == '测试报告'
    assert data['content'] == '# 测试\n内容'


def test_report_not_found(client):
    resp = client.get('/api/report/99999')
    assert resp.status_code == 404


def test_report_delete(client):
    db = get_db()
    db.execute(
        "INSERT INTO reports (title, date_from, date_to, content) VALUES (?, ?, ?, ?)",
        ('删除测试', '2026-01-01', '2026-02-01', 'content')
    )
    db.commit()
    db.close()

    resp = client.get('/api/reports')
    report_id = resp.json[0]['id']

    resp = client.delete(f'/api/report/{report_id}')
    assert resp.status_code == 200
    assert resp.json['status'] == 'ok'

    resp = client.get('/api/reports')
    assert resp.json == []


def test_stats_with_date_filter(client):
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance, avg_heart_rate, avg_pace)
        VALUES
        (201, 'Run May', 'running', '2026-05-01 07:00:00', 1800, 5000, 145, 360),
        (202, 'Run Jan', 'running', '2026-01-15 08:00:00', 3600, 10000, 150, 340)
    """)
    db.commit()
    db.close()

    resp = client.get('/api/stats?from=2026-04-01&to=2026-06-01')
    data = resp.json
    assert data['overview']['total_runs'] == 1
    assert data['overview']['total_distance'] == 5000

    resp = client.get('/api/stats')
    data = resp.json
    assert data['overview']['total_runs'] == 2


def test_config_profile_keys(client):
    resp = client.post('/api/config', json={
        'profile_age': '28',
        'profile_gender': 'male',
        'profile_weight': '65',
        'profile_race_goal': 'half_marathon',
    })
    assert resp.status_code == 200

    resp = client.get('/api/config')
    data = resp.json
    assert data['profile_age'] == '28'
    assert data['profile_gender'] == 'male'
    assert data['profile_weight'] == '65'
    assert data['profile_race_goal'] == 'half_marathon'
