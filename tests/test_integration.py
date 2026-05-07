"""端到端集成测试"""


def test_full_workflow(client):
    resp = client.get('/api/ping')
    assert resp.status_code == 200

    resp = client.get('/api/stats')
    assert resp.status_code == 200
    assert resp.json['overview']['total_runs'] == 0

    resp = client.get('/api/activities')
    assert resp.status_code == 200
    assert len(resp.json) == 0

    resp = client.get('/api/chat/history')
    assert resp.status_code == 200
    assert len(resp.json) == 0

    resp = client.post('/api/config', json={'llm_model': 'test-model'})
    assert resp.status_code == 200

    resp = client.get('/api/config')
    assert resp.status_code == 200


def test_frontend_served(client):
    resp = client.get('/')
    assert resp.status_code == 200
    content = resp.data.decode('utf-8')
    assert 'Running AI Coach' in content
    assert 'chart.js' in content.lower()
    assert 'marked' in content.lower()


def test_css_served(client):
    resp = client.get('/css/style.css')
    assert resp.status_code == 200


def test_js_served(client):
    for js_file in ['app.js', 'api.js', 'dashboard.js', 'activities.js', 'report.js', 'chat.js', 'settings.js']:
        resp = client.get(f'/js/{js_file}')
        assert resp.status_code == 200, f'{js_file} should be served'
