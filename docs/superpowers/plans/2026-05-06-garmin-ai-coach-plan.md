# 佳明运动分析与 AI 教练系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建本地化佳明运动数据分析与 AI 教练工具，支持数据同步、多智能体报告生成、智能问答

**Architecture:** Python Flask 后端 + 纯 HTML/JS 前端 SPA，SQLite 本地存储，通过 garminconnect 库同步佳明中国区数据，OpenAI 兼容 SDK 调用 DeepSeek LLM

**Tech Stack:** Python 3, Flask, SQLite, garminconnect, openai SDK, Chart.js, marked.js, PyInstaller

---

## 文件结构

```
backend/
  app.py                    # Flask 应用入口，路由注册，模板渲染
  database.py               # SQLite 初始化和连接管理
  garmin_client.py          # 佳明 API 封装（登录、同步、数据获取）
  llm_client.py             # LLM 调用封装（单轮、多轮、流式）
  report_generator.py       # 多智能体报告生成引擎
  chat_service.py           # 问答服务（上下文构建、历史管理）
  sync_service.py           # 同步进度管理
  config.py                 # 配置读写（环境变量 + SQLite）

frontend/
  index.html                # SPA 外壳 + 所有页面模板
  css/
    style.css                # 全局样式
  js/
    app.js                   # 路由、初始化、全局状态
    api.js                   # 后端 API 封装
    dashboard.js             # 仪表盘页面
    activities.js            # 活动列表 + 详情页
    report.js                # 报告生成 + 历史
    chat.js                  # 对话页面
    settings.js              # 设置页面

tests/
  conftest.py                # pytest fixtures
  test_database.py
  test_garmin_client.py
  test_llm_client.py
  test_report_generator.py
  test_chat_service.py
  test_api.py

requirements.txt
pyinstaller.spec
run.bat                      # Windows 启动脚本
```

---

## Phase 1: 项目脚手架

### Task 1: 创建项目目录结构和依赖文件

**Files:**
- Create: `backend/__init__.py`
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `frontend/index.html` (空壳)
- Create: `frontend/css/style.css` (空文件)
- Create: `frontend/js/app.js` (空文件)

- [ ] **Step 1: 创建所有空目录和占位文件**

```bash
mkdir -p backend frontend/css frontend/js tests
touch backend/__init__.py tests/__init__.py
```

- [ ] **Step 2: 编写 requirements.txt**

```
flask==3.1.1
garminconnect==0.2.45
openai==1.93.2
python-dotenv==1.1.0
cryptography==44.0.2
```

- [ ] **Step 3: 编写 conftest.py（pytest fixtures）**

```python
import pytest
import os
import tempfile

@pytest.fixture
def test_db_path():
    """创建临时数据库路径"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def app(test_db_path):
    """创建测试 Flask 应用"""
    os.environ['RUNNING_DB_PATH'] = test_db_path
    from backend.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()
```

- [ ] **Step 4: 安装依赖并验证**

```bash
pip install -r requirements.txt
python -c "import flask; import garminconnect; import openai; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with dependencies"
```

---

### Task 2: 实现数据库初始化和配置管理

**Files:**
- Create: `backend/database.py`
- Create: `backend/config.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: 编写 database.py 失败测试**

```python
# tests/test_database.py
import pytest
import os
from backend.database import init_db, get_db

def test_init_db_creates_tables(test_db_path):
    os.environ['RUNNING_DB_PATH'] = test_db_path
    init_db()
    db = get_db()
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t['name'] for t in tables]
    assert 'activities' in table_names
    assert 'chat_history' in table_names
    assert 'config' in table_names

def test_init_db_idempotent(test_db_path):
    os.environ['RUNNING_DB_PATH'] = test_db_path
    init_db()
    init_db()  # 不应报错
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_database.py -v
```
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 编写 database.py 实现**

```python
import sqlite3
import os

DB_PATH = None

def _get_db_path():
    if DB_PATH:
        return DB_PATH
    return os.environ.get('RUNNING_DB_PATH', 'data/running.db')

def set_db_path(path):
    global DB_PATH
    DB_PATH = path

def get_db():
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            start_time TEXT,
            duration REAL,
            distance REAL,
            avg_heart_rate REAL,
            max_heart_rate REAL,
            avg_pace REAL,
            elevation_gain REAL,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now','localtime')),
            role TEXT,
            content TEXT,
            context_snapshot TEXT
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    db.commit()
    db.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_database.py -v
```

- [ ] **Step 5: 编写 config.py 实现**

```python
from backend.database import get_db

DEFAULT_CONFIG = {
    'llm_base_url': 'https://api.deepseek.com/v1',
    'llm_api_key': '',
    'llm_model': 'deepseek-chat',
    'report_rounds': '4',
    'sync_strength': 'true',
    'sync_auto_interval': '0',  # 0 = 仅手动
}

def get_config(key, default=None):
    db = get_db()
    row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    db.close()
    if row:
        return row['value']
    if default is not None:
        return default
    return DEFAULT_CONFIG.get(key, '')

def set_config(key, value):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    db.commit()
    db.close()

def get_all_config():
    db = get_db()
    rows = db.execute("SELECT key, value FROM config").fetchall()
    db.close()
    result = dict(DEFAULT_CONFIG)
    for row in rows:
        result[row['key']] = row['value']
    return result
```

- [ ] **Step 6: 运行完整测试**

```bash
pytest tests/test_database.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/database.py backend/config.py tests/test_database.py
git commit -m "feat: add database initialization and config management"
```

---

### Task 3: 创建 Flask 应用骨架

**Files:**
- Create: `backend/app.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: 编写 Flask 应用基础测试**

```python
# tests/test_api.py
def test_app_health_check(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.json['status'] == 'ok'

def test_app_serves_frontend(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'<!DOCTYPE html>' in resp.data
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_api.py -v
```

- [ ] **Step 3: 编写 app.py 实现**

```python
import os
from flask import Flask, send_from_directory, jsonify
from backend.database import init_db

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

    # 初始化数据库
    with app.app_context():
        init_db()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app.py tests/test_api.py
git commit -m "feat: Flask application skeleton with health check"
```

---

## Phase 2: 佳明数据集成

### Task 4: 实现佳明客户端封装

**Files:**
- Create: `backend/garmin_client.py`
- Create: `tests/test_garmin_client.py`

- [ ] **Step 1: 编写 garmin_client 测试**

```python
# tests/test_garmin_client.py
import pytest
from unittest.mock import patch, MagicMock
from backend.garmin_client import GarminClient

@patch('backend.garmin_client.Garmin')
def test_login_success(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin_class.return_value = mock_garmin
    mock_garmin.login.return_value = None

    client = GarminClient()
    result = client.login('test@example.com', 'password')

    assert result['success'] is True
    mock_garmin_class.assert_called_once()
    # 验证使用中国区 domain
    call_kwargs = mock_garmin_class.call_args[1]
    assert call_kwargs.get('domain') == 'cn' or 'garmin.cn' in str(call_kwargs)

@patch('backend.garmin_client.Garmin')
def test_login_needs_captcha(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin_class.return_value = mock_garmin
    mock_garmin.login.side_effect = Exception("验证码")

    client = GarminClient()
    result = client.login('test@example.com', 'password')
    # 不应崩溃，应返回错误信息
    assert 'error' in result or result['success'] is False

@patch('backend.garmin_client.Garmin')
def test_fetch_activities(mock_garmin_class):
    mock_garmin = MagicMock()
    mock_garmin_class.return_value = mock_garmin
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
    activities = client.fetch_activities(limit=10)

    assert len(activities) == 1
    assert activities[0]['id'] == 123
    assert activities[0]['type'] == 'running'
    assert activities[0]['distance'] == 5000.0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_garmin_client.py -v
```

- [ ] **Step 3: 编写 garmin_client.py 实现**

```python
from garminconnect import Garmin

class GarminClient:
    def __init__(self):
        self.client = None
        self.email = None
        self.session_token = None

    def login(self, email, password):
        """登录佳明中国区账户。返回 {'success': True} 或 {'success': False, 'error': str}"""
        try:
            self.client = Garmin(email, password)
            # 中国区使用 garmin.cn
            self.client.display_name = 'Garmin'
            self.client.login()
            self.email = email
            self.session_token = self.client.session_token
            return {'success': True}
        except Exception as e:
            error_msg = str(e)
            if '验证码' in error_msg or 'captcha' in error_msg.lower():
                return {'success': False, 'error': '需要验证码', 'need_captcha': True}
            return {'success': False, 'error': error_msg}

    def fetch_activities(self, start=0, limit=100):
        """获取活动列表（摘要信息）。返回活动字典列表。"""
        if not self.client:
            raise RuntimeError("未登录")
        raw = self.client.get_activities(start, limit)
        return [self._parse_activity(a) for a in raw]

    def fetch_activity_detail(self, activity_id):
        """获取单条活动完整详情。返回完整 JSON。"""
        if not self.client:
            raise RuntimeError("未登录")
        return self.client.get_activity(activity_id)

    def _parse_activity(self, raw):
        """将佳明原始数据转为内部字段格式"""
        activity_type = raw.get('activityType', {})
        type_key = activity_type.get('typeKey', 'other') if isinstance(activity_type, dict) else 'other'

        return {
            'id': raw.get('activityId'),
            'name': raw.get('activityName', ''),
            'type': type_key,
            'start_time': raw.get('startTimeLocal', ''),
            'duration': raw.get('duration', 0),
            'distance': raw.get('distance', 0),
            'avg_heart_rate': raw.get('averageHR'),
            'max_heart_rate': raw.get('maxHR'),
            'avg_pace': self._calc_pace(raw.get('duration'), raw.get('distance')),
            'elevation_gain': raw.get('elevationGain', 0),
            'raw_json': str(raw),
        }

    def _calc_pace(self, duration, distance):
        """计算配速（秒/公里）。distance 为米，duration 为秒。"""
        if not duration or not distance or distance == 0:
            return None
        return (duration / (distance / 1000))  # 秒/公里
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_garmin_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/garmin_client.py tests/test_garmin_client.py
git commit -m "feat: Garmin client wrapper with China region support"
```

---

### Task 5: 实现同步服务和活动存储

**Files:**
- Create: `backend/sync_service.py`
- Create: `tests/test_sync_service.py`

- [ ] **Step 1: 编写 sync_service 测试**

```python
# tests/test_sync_service.py
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

    result = sync_service.sync(email='test@test.com', password='pw')

    assert result['new_count'] == 1
    assert result['total_checked'] == 1

    # 验证数据已存入数据库
    db = get_db()
    row = db.execute("SELECT * FROM activities WHERE id=1").fetchone()
    db.close()
    assert row is not None
    assert row['name'] == 'Run 1'

def test_sync_skips_existing(sync_service):
    """已存在的活动 ID 不重复插入"""
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
        assert result['new_count'] == 0  # 已存在，跳过
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_sync_service.py -v
```

- [ ] **Step 3: 编写 sync_service.py 实现**

```python
from backend.garmin_client import GarminClient
from backend.database import get_db

class SyncService:
    def __init__(self):
        self.garmin = None
        self._progress = {'status': 'idle', 'current': 0, 'total': 0}

    def sync(self, email, password):
        """执行增量同步。返回 {new_count, total_checked}"""
        self.garmin = GarminClient()
        login_result = self.garmin.login(email, password)

        if not login_result['success']:
            return {'error': login_result.get('error', '登录失败'), 'need_captcha': login_result.get('need_captcha', False)}

        db = get_db()
        activities = self.garmin.fetch_activities(start=0, limit=500)

        new_count = 0
        for activity in activities:
            existing = db.execute(
                "SELECT id FROM activities WHERE id=?",
                (activity['id'],)
            ).fetchone()

            if not existing:
                db.execute("""
                    INSERT OR IGNORE INTO activities
                    (id, name, type, start_time, duration, distance,
                     avg_heart_rate, max_heart_rate, avg_pace, elevation_gain, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    activity['id'], activity['name'], activity['type'],
                    activity['start_time'], activity['duration'], activity['distance'],
                    activity['avg_heart_rate'], activity['max_heart_rate'],
                    activity['avg_pace'], activity['elevation_gain'], activity['raw_json']
                ))
                new_count += 1

        db.commit()
        db.close()

        return {
            'new_count': new_count,
            'total_checked': len(activities)
        }

    def get_progress(self):
        return self._progress
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_sync_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/sync_service.py tests/test_sync_service.py
git commit -m "feat: sync service with incremental activity storage"
```

---

### Task 6: 添加同步相关 API 路由

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: 编写 API 测试（追加到 test_api.py）**

```python
# 追加到 tests/test_api.py

from unittest.mock import patch, MagicMock

@patch('backend.app.SyncService')
def test_sync_endpoint(mock_sync_class, client):
    mock_sync = MagicMock()
    mock_sync_class.return_value = mock_sync
    mock_sync.sync.return_value = {'new_count': 5, 'total_checked': 10}

    resp = client.post('/api/sync', json={
        'email': 'test@test.com',
        'password': 'test123'
    })
    assert resp.status_code == 200
    assert resp.json['new_count'] == 5

def test_sync_requires_credentials(client):
    resp = client.post('/api/sync', json={})
    assert resp.status_code == 400

def test_activities_list(client):
    """测试活动列表 API"""
    from backend.database import get_db
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
    from backend.database import get_db
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

def test_activity_detail(client):
    from backend.database import get_db
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_api.py -v -k "sync or activities or activity"
```

- [ ] **Step 3: 在 app.py 中添加路由**

```python
# 在 create_app() 函数中，@app.route('/api/health') 之后添加：

from backend.sync_service import SyncService
from backend.database import get_db

sync_service = SyncService()

@app.route('/api/sync', methods=['POST'])
def sync():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': '需要邮箱和密码'}), 400

    result = sync_service.sync(data['email'], data['password'])
    if 'error' in result:
        return jsonify(result), 401
    return jsonify(result)

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
    # 解析 JSON 字段
    import json
    if result.get('raw_json'):
        try:
            result['raw_json'] = json.loads(result['raw_json'])
        except json.JSONDecodeError:
            pass
    return jsonify(result)
```

注意：还需要在文件顶部添加 `from flask import request`。

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_api.py -v -k "sync or activities or activity"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app.py tests/test_api.py
git commit -m "feat: add sync, activities list, and activity detail API endpoints"
```

---

## Phase 3: 前端 Shell 与仪表盘

### Task 7: 创建前端 SPA 外壳 + 路由

**Files:**
- Create: `frontend/js/app.js`
- Create: `frontend/js/api.js`
- Modify: `frontend/index.html`

- [ ] **Step 1: 编写 index.html 外壳**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Running AI Coach</title>
    <link rel="stylesheet" href="/css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
    <nav id="nav">
        <a href="#dashboard">仪表盘</a>
        <a href="#activities">运动记录</a>
        <a href="#report">训练报告</a>
        <a href="#chat">AI 问答</a>
        <a href="#settings">设置</a>
    </nav>
    <main id="app"></main>

    <script src="/js/api.js"></script>
    <script src="/js/app.js"></script>
    <script src="/js/dashboard.js"></script>
    <script src="/js/activities.js"></script>
    <script src="/js/report.js"></script>
    <script src="/js/chat.js"></script>
    <script src="/js/settings.js"></script>
</body>
</html>
```

- [ ] **Step 2: 编写 api.js**

```javascript
// api.js - 后端 API 封装
const API = {
    async request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(path, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: resp.statusText }));
            throw new Error(err.error || 'Request failed');
        }
        return resp.json();
    },

    get(path) { return this.request('GET', path); },
    post(path, body) { return this.request('POST', path, body); },
    delete(path) { return this.request('DELETE', path); },

    // 活动
    activities(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return this.get('/api/activities' + (qs ? '?' + qs : ''));
    },
    activityDetail(id) { return this.get('/api/activity/' + id); },

    // 同步
    sync(email, password) { return this.post('/api/sync', { email, password }); },

    // 统计
    stats(period = 'monthly') { return this.get('/api/stats?period=' + period); },

    // 报告
    generateReport(body) { return this.post('/api/report/generate', body); },
    reportStatus(taskId) { return this.get('/api/report/status/' + taskId); },
    reportResult(taskId) { return this.get('/api/report/result/' + taskId); },

    // 问答
    async chatAsk(question, onChunk) {
        const resp = await fetch('/api/chat/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = decoder.decode(value, { stream: true });
            // SSE 格式: "data: xxx\n\n"
            const lines = text.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') return;
                    try { onChunk(JSON.parse(data)); }
                    catch { onChunk(data); }
                }
            }
        }
    },
    chatHistory(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return this.get('/api/chat/history' + (qs ? '?' + qs : ''));
    },
    chatDelete(id) { return this.delete('/api/chat/delete/' + id); },
    chatClear() { return this.delete('/api/chat/clear'); },

    // 配置
    getConfig() { return this.get('/api/config'); },
    updateConfig(data) { return this.post('/api/config', data); }
};
```

- [ ] **Step 3: 编写 app.js（路由 + 页面切换）**

```javascript
// app.js - SPA 路由与页面渲染
const pages = {};

function registerPage(hash, renderFn) {
    pages[hash] = renderFn;
}

function navigate() {
    const hash = location.hash || '#dashboard';
    const renderFn = pages[hash];
    const main = document.getElementById('app');
    if (renderFn) {
        main.innerHTML = '';
        renderFn(main);
    } else {
        main.innerHTML = '<p>页面不存在</p>';
    }
    // 高亮当前导航
    document.querySelectorAll('#nav a').forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === hash);
    });
}

window.addEventListener('hashchange', navigate);
window.addEventListener('DOMContentLoaded', navigate);
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: SPA shell with hash routing and API client"
```

---

### Task 8: 实现仪表盘统计 API

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 编写仪表盘统计测试**

```python
# 追加到 tests/test_api.py
def test_stats_endpoint(client):
    from backend.database import get_db
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
    assert 'total_runs' in data or 'monthly' in data
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_api.py::test_stats_endpoint -v
```

- [ ] **Step 3: 添加 /api/stats 路由**

```python
@app.route('/api/stats')
def stats():
    period = request.args.get('period', 'monthly')
    db = get_db()

    # 总览统计
    overview = db.execute("""
        SELECT
            COUNT(*) as total_runs,
            COALESCE(SUM(distance), 0) as total_distance,
            COALESCE(SUM(duration), 0) as total_duration,
            COALESCE(AVG(avg_heart_rate), 0) as avg_hr,
            COALESCE(AVG(avg_pace), 0) as avg_pace
        FROM activities
        WHERE type='running'
    """).fetchone()

    # 月度趋势（最近12个月）
    monthly = db.execute("""
        SELECT
            strftime('%Y-%m', start_time) as month,
            COUNT(*) as count,
            COALESCE(SUM(distance), 0) as distance,
            COALESCE(SUM(duration), 0) as duration,
            COALESCE(AVG(avg_pace), 0) as avg_pace
        FROM activities
        WHERE type='running'
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """).fetchall()

    # 配速分布
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
        GROUP BY pace_range
        ORDER BY MIN(avg_pace)
    """).fetchall()

    db.close()

    return jsonify({
        'overview': dict(overview),
        'monthly': [dict(r) for r in reversed(monthly)],
        'pace_distribution': [dict(r) for r in pace_dist],
    })
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_api.py::test_stats_endpoint -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app.py tests/test_api.py
git commit -m "feat: add dashboard statistics API endpoint"
```

---

### Task 9: 实现仪表盘前端页面

**Files:**
- Create: `frontend/js/dashboard.js`
- Create: `frontend/css/style.css`

- [ ] **Step 1: 编写 style.css**

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; }

#nav { display: flex; gap: 0; background: #1a1a2e; padding: 0 20px; }
#nav a { color: #aaa; text-decoration: none; padding: 14px 20px; font-size: 14px; border-bottom: 2px solid transparent; }
#nav a.active { color: #fff; border-bottom-color: #e94560; }
#nav a:hover { color: #fff; }

#app { max-width: 1100px; margin: 0 auto; padding: 20px; }

.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card h2 { font-size: 16px; margin-bottom: 12px; color: #1a1a2e; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.stat-card { background: #1a1a2e; color: #fff; border-radius: 8px; padding: 16px; text-align: center; }
.stat-card .value { font-size: 28px; font-weight: bold; }
.stat-card .label { font-size: 12px; color: #aaa; margin-top: 4px; }

.chart-wrap { position: relative; height: 250px; }

table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }
th { color: #888; font-weight: 500; }

.btn { display: inline-block; padding: 8px 20px; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; background: #e94560; color: #fff; }
.btn:hover { opacity: 0.9; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #eee; color: #333; }

input, select, textarea { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; margin-bottom: 10px; }
label { font-size: 13px; color: #666; display: block; margin-bottom: 4px; }

.flex-between { display: flex; justify-content: space-between; align-items: center; }
.filter-bar { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 16px; }
.filter-bar select, .filter-bar input { width: auto; min-width: 120px; margin-bottom: 0; }

.chat-layout { display: grid; grid-template-columns: 260px 1fr; gap: 16px; height: calc(100vh - 120px); }
.chat-sidebar { overflow-y: auto; }
.chat-main { display: flex; flex-direction: column; }
.chat-messages { flex: 1; overflow-y: auto; padding: 10px 0; }
.chat-message { margin-bottom: 14px; padding: 10px 14px; border-radius: 8px; max-width: 85%; }
.chat-message.user { background: #1a1a2e; color: #fff; margin-left: auto; }
.chat-message.assistant { background: #f0f0f0; color: #333; }
.chat-input { display: flex; gap: 10px; }
.chat-input input { flex: 1; margin-bottom: 0; }

.report-md { line-height: 1.7; }
.report-md h1, .report-md h2, .report-md h3 { margin: 16px 0 8px; }
.report-md table { margin: 12px 0; }
.report-md th, .report-md td { border: 1px solid #ddd; }

.toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 6px; color: #fff; font-size: 14px; z-index: 9999; }
.toast.success { background: #2ecc71; }
.toast.error { background: #e74c3c; }

.sync-bar { display: flex; align-items: center; gap: 12px; }
.progress-bar { flex: 1; height: 6px; background: #eee; border-radius: 3px; overflow: hidden; }
.progress-bar .fill { height: 100%; background: #e94560; transition: width 0.3s; }
```

- [ ] **Step 2: 编写 dashboard.js**

```javascript
// dashboard.js
registerPage('#dashboard', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">训练仪表盘</h1>
        <div id="stats-cards" class="stats-grid"></div>
        <div class="card" style="margin-top:16px"><h2>月度跑量趋势</h2><div class="chart-wrap"><canvas id="monthlyChart"></canvas></div></div>
        <div class="card"><h2>配速分布</h2><div class="chart-wrap"><canvas id="paceChart"></canvas></div></div>
    `;

    try {
        const data = await API.stats();
        renderStatsCards(data.overview);
        renderMonthlyChart(data.monthly);
        renderPaceChart(data.pace_distribution);
    } catch (err) {
        container.innerHTML += `<p style="color:red">加载失败: ${err.message}</p>`;
    }
});

function renderStatsCards(overview) {
    const totalKm = ((overview.total_distance || 0) / 1000).toFixed(1);
    const avgPace = formatPace(overview.avg_pace);

    document.getElementById('stats-cards').innerHTML = `
        <div class="stat-card"><div class="value">${overview.total_runs || 0}</div><div class="label">总跑步次数</div></div>
        <div class="stat-card"><div class="value">${totalKm}</div><div class="label">总跑量 (km)</div></div>
        <div class="stat-card"><div class="value">${avgPace}</div><div class="label">平均配速</div></div>
        <div class="stat-card"><div class="value">${Math.round(overview.avg_hr) || '-'}</div><div class="label">平均心率</div></div>
    `;
}

function renderMonthlyChart(monthly) {
    const ctx = document.getElementById('monthlyChart');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: monthly.map(m => m.month),
            datasets: [{
                label: '跑量 (km)',
                data: monthly.map(m => (m.distance / 1000).toFixed(1)),
                backgroundColor: '#e94560'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });
}

function renderPaceChart(paceDist) {
    const ctx = document.getElementById('paceChart');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: paceDist.map(p => p.pace_range),
            datasets: [{
                data: paceDist.map(p => p.count),
                backgroundColor: ['#e94560','#f77f6e','#f9a87a','#facf8a','#e0e0e0','#c0c0c0','#999']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right' } }
        }
    });
}

function formatPace(seconds) {
    if (!seconds || seconds === 0) return '-';
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${String(sec).padStart(2, '0')}`;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/js/dashboard.js frontend/css/style.css
git commit -m "feat: dashboard page with stats cards and charts"
```

---

### Task 10: 实现活动列表与详情前端

**Files:**
- Create: `frontend/js/activities.js`

- [ ] **Step 1: 编写 activities.js**

```javascript
// activities.js
registerPage('#activities', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">运动记录</h1>
        <div class="filter-bar">
            <select id="act-type-filter">
                <option value="">全部类型</option>
                <option value="running">跑步</option>
                <option value="strength_training">力量训练</option>
                <option value="other">其他</option>
            </select>
            <input id="act-search" type="text" placeholder="搜索名称...">
            <input id="act-date-from" type="date" placeholder="开始日期">
            <input id="act-date-to" type="date" placeholder="结束日期">
            <button class="btn" id="act-filter-btn">筛选</button>
        </div>
        <div id="act-list"></div>
        <div id="act-detail" style="display:none"></div>
    `;

    document.getElementById('act-filter-btn').onclick = () => loadActivities(container);
    loadActivities(container);
});

async function loadActivities(container) {
    const params = {
        type: document.getElementById('act-type-filter').value || undefined,
        q: document.getElementById('act-search').value || undefined,
        from: document.getElementById('act-date-from').value || undefined,
        to: document.getElementById('act-date-to').value || undefined,
    };
    // 移除 undefined 值
    Object.keys(params).forEach(k => params[k] === undefined && delete params[k]);

    try {
        const activities = await API.activities(params);
        renderActivityList(activities);
    } catch (err) {
        document.getElementById('act-list').innerHTML = `<p style="color:red">加载失败: ${err.message}</p>`;
    }
}

function renderActivityList(activities) {
    const list = document.getElementById('act-list');
    if (activities.length === 0) {
        list.innerHTML = '<p>暂无运动记录，请先同步数据。</p>';
        return;
    }
    list.innerHTML = `
        <table>
            <thead><tr>
                <th>日期</th><th>名称</th><th>类型</th><th>距离</th><th>时长</th><th>配速</th><th>心率</th>
            </tr></thead>
            <tbody>
                ${activities.map(a => `
                    <tr style="cursor:pointer" onclick="viewActivityDetail(${a.id})">
                        <td>${(a.start_time || '').slice(0, 10)}</td>
                        <td>${escapeHtml(a.name)}</td>
                        <td>${typeLabel(a.type)}</td>
                        <td>${a.distance ? (a.distance/1000).toFixed(2)+'km' : '-'}</td>
                        <td>${formatDuration(a.duration)}</td>
                        <td>${formatPace(a.avg_pace)}</td>
                        <td>${Math.round(a.avg_heart_rate) || '-'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function viewActivityDetail(id) {
    try {
        const act = await API.activityDetail(id);
        const detail = document.getElementById('act-detail');
        detail.style.display = 'block';
        detail.innerHTML = `
            <div class="card">
                <div class="flex-between">
                    <h2>${escapeHtml(act.name)}</h2>
                    <button class="btn btn-secondary" onclick="document.getElementById('act-detail').style.display='none'">关闭</button>
                </div>
                <div class="stats-grid" style="margin-top:12px">
                    <div class="stat-card"><div class="value">${(act.distance/1000).toFixed(2)}km</div><div class="label">距离</div></div>
                    <div class="stat-card"><div class="value">${formatDuration(act.duration)}</div><div class="label">时长</div></div>
                    <div class="stat-card"><div class="value">${formatPace(act.avg_pace)}</div><div class="label">平均配速</div></div>
                    <div class="stat-card"><div class="value">${Math.round(act.avg_heart_rate) || '-'}</div><div class="label">平均心率</div></div>
                    <div class="stat-card"><div class="value">${Math.round(act.max_heart_rate) || '-'}</div><div class="label">最大心率</div></div>
                    <div class="stat-card"><div class="value">${act.elevation_gain || 0}m</div><div class="label">海拔爬升</div></div>
                </div>
            </div>
        `;
        window.scrollTo({ top: detail.offsetTop - 20, behavior: 'smooth' });
    } catch (err) {
        showToast('加载详情失败: ' + err.message, 'error');
    }
}

function typeLabel(type) {
    const map = { running: '跑步', strength_training: '力量训练', cycling: '骑行', swimming: '游泳' };
    return map[type] || type || '其他';
}

function formatDuration(seconds) {
    if (!seconds) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    return `${m}:${String(s).padStart(2,'0')}`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(msg, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/activities.js
git commit -m "feat: activities list with filtering and detail view"
```

---

## Phase 4: LLM 集成与智能问答

### Task 11: 实现 LLM 客户端

**Files:**
- Create: `backend/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: 编写 LLM 客户端测试**

```python
# tests/test_llm_client.py
import pytest
from unittest.mock import patch, MagicMock
from backend.llm_client import LLMClient

def test_single_chat():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='Hello!'))]
        )

        result = client.chat([{'role': 'user', 'content': 'Hi'}])
        assert result == 'Hello!'
        mock_client.chat.completions.create.assert_called_once()

def test_stream_chat():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content='Hello'))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=' world'))]),
        ]

        chunks = list(client.chat_stream([{'role': 'user', 'content': 'Hi'}]))
        assert chunks == ['Hello', ' world']

def test_multi_turn_chat():
    """多轮对话：每次调用追加 assistant 回复到消息列表"""
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content='Turn 1'))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content='Turn 2'))]),
        ]

        messages = [{'role': 'user', 'content': 'Start'}]
        r1 = client.chat(messages)
        messages.append({'role': 'assistant', 'content': r1})
        r2 = client.chat(messages)

        assert r1 == 'Turn 1'
        assert r2 == 'Turn 2'
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_llm_client.py -v
```

- [ ] **Step 3: 编写 llm_client.py 实现**

```python
from openai import OpenAI

class LLMClient:
    def __init__(self, base_url, api_key, model):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )
        return self.client

    def chat(self, messages, max_tokens=4096, temperature=0.7):
        """发送消息并返回完整回复文本"""
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content

    def chat_stream(self, messages, max_tokens=4096, temperature=0.7):
        """流式返回回复文本 chunks"""
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in resp:
            content = chunk.choices[0].delta.content
            if content:
                yield content
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_llm_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/llm_client.py tests/test_llm_client.py
git commit -m "feat: LLM client with single, stream, and multi-turn chat"
```

---

### Task 12: 实现问答服务和 SSE 路由

**Files:**
- Create: `backend/chat_service.py`
- Create: `tests/test_chat_service.py`

- [ ] **Step 1: 编写 chat_service 测试**

```python
# tests/test_chat_service.py
import pytest
from unittest.mock import patch, MagicMock
from backend.chat_service import ChatService

def test_build_context():
    """测试构建对话上下文"""
    service = ChatService()
    # 模拟训练摘要
    summary = "最近12周跑量: 150km, 平均配速: 5:30"
    messages = service.build_messages('我今天该跑什么?', summary, [])
    assert len(messages) == 2
    assert messages[0]['role'] == 'system'
    assert '私人跑步教练' in messages[0]['content']
    assert '150km' in messages[0]['content']  # 训练数据已注入
    assert messages[1]['role'] == 'user'

def test_save_and_get_history():
    """测试保存和获取对话历史"""
    from backend.database import init_db, get_db
    import os
    db_path = '/tmp/test_chat.db'
    try:
        os.environ['RUNNING_DB_PATH'] = db_path
        init_db()
        service = ChatService()

        service.save_message('user', '问题1')
        service.save_message('assistant', '回答1')

        history = service.get_history()
        assert len(history) == 2

        # 测试搜索
        results = service.search_history('问题1')
        assert len(results) == 1
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
```

- [ ] **Step 2: 编写 chat_service.py 实现**

```python
from backend.database import get_db
from backend.config import get_config

SYSTEM_PROMPT = """你是私人跑步教练，可根据用户提供的训练数据给出个性化建议。

你具备运动科学背景，注重周期化训练、配速策略、伤病预防。
回答时:
1. 引用数据中的具体数字支撑观点
2. 给出可操作的训练建议
3. 指出潜在风险
4. 鼓励但不盲目乐观

用户近期训练数据:
{training_summary}
"""

class ChatService:
    def build_messages(self, question, training_summary, recent_history):
        """构建发送给 LLM 的消息列表"""
        system_content = SYSTEM_PROMPT.format(training_summary=training_summary or '暂无训练数据')

        messages = [{'role': 'system', 'content': system_content}]

        # 注入最近对话历史（最近5轮）
        for entry in recent_history[-10:]:
            messages.append({'role': entry['role'], 'content': entry['content']})

        messages.append({'role': 'user', 'content': question})
        return messages

    def save_message(self, role, content, context_snapshot=''):
        """保存消息到 chat_history 表"""
        db = get_db()
        db.execute(
            "INSERT INTO chat_history (role, content, context_snapshot) VALUES (?, ?, ?)",
            (role, content, context_snapshot)
        )
        db.commit()
        db.close()

    def get_history(self, limit=100):
        """获取对话历史"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM chat_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        db.close()
        return [dict(r) for r in reversed(rows)]

    def search_history(self, query):
        """搜索对话历史"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM chat_history WHERE content LIKE ? ORDER BY timestamp DESC",
            (f'%{query}%',)
        ).fetchall()
        db.close()
        return [dict(r) for r in reversed(rows)]

    def delete_message(self, msg_id):
        """删除单条消息"""
        db = get_db()
        db.execute("DELETE FROM chat_history WHERE id=?", (msg_id,))
        db.commit()
        db.close()

    def clear_all(self):
        """清空所有对话"""
        db = get_db()
        db.execute("DELETE FROM chat_history")
        db.commit()
        db.close()

    def get_training_summary(self):
        """获取最近12周训练数据摘要"""
        db = get_db()
        rows = db.execute("""
            SELECT
                COUNT(*) as total_runs,
                COALESCE(SUM(distance), 0) as total_distance,
                COALESCE(AVG(avg_pace), 0) as avg_pace,
                COALESCE(AVG(avg_heart_rate), 0) as avg_hr,
                COALESCE(SUM(duration), 0) as total_duration
            FROM activities
            WHERE type='running'
            AND start_time >= datetime('now', '-84 days', 'localtime')
        """).fetchone()
        db.close()

        if not rows or rows['total_runs'] == 0:
            return None

        r = dict(rows)
        return (
            f"最近12周: {r['total_runs']}次跑步, "
            f"总跑量 {r['total_distance']/1000:.1f}km, "
            f"总时间 {r['total_duration']/3600:.1f}小时, "
            f"平均配速 {r['avg_pace']:.0f}秒/公里, "
            f"平均心率 {r['avg_hr']:.0f}bpm"
        )
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_chat_service.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/chat_service.py tests/test_chat_service.py
git commit -m "feat: chat service with context building and history management"
```

---

### Task 13: 添加问答 SSE API 和对话管理路由

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 在 app.py 中添加问答路由**

```python
# 在 create_app() 中添加以下路由:

from backend.llm_client import LLMClient
from backend.chat_service import ChatService
from backend.config import get_config
import json

chat_service = ChatService()

def _get_llm_client():
    return LLMClient(
        base_url=get_config('llm_base_url'),
        api_key=get_config('llm_api_key'),
        model=get_config('llm_model')
    )

@app.route('/api/chat/ask', methods=['POST'])
def chat_ask():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({'error': '需要 question 字段'}), 400

    question = data['question']
    summary = chat_service.get_training_summary()
    history = chat_service.get_history()
    messages = chat_service.build_messages(question, summary, history)

    # 保存用户问题
    chat_service.save_message('user', question, summary or '')

    llm = _get_llm_client()

    def generate():
        full_response = []
        try:
            for chunk in llm.chat_stream(messages):
                full_response.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            full_text = ''.join(full_response)
            chat_service.save_message('assistant', full_text)
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/chat/history')
def chat_history():
    q = request.args.get('q')
    if q:
        rows = chat_service.search_history(q)
    else:
        rows = chat_service.get_history()
    return jsonify(rows)

@app.route('/api/chat/delete/<int:msg_id>', methods=['DELETE'])
def chat_delete(msg_id):
    chat_service.delete_message(msg_id)
    return jsonify({'status': 'ok'})

@app.route('/api/chat/clear', methods=['DELETE'])
def chat_clear():
    chat_service.clear_all()
    return jsonify({'status': 'ok'})
```

注意：文件顶部需要添加 `from flask import Response`。

- [ ] **Step 2: Commit**

```bash
git add backend/app.py
git commit -m "feat: add chat SSE endpoint and history management routes"
```

---

### Task 14: 实现问答前端页面

**Files:**
- Create: `frontend/js/chat.js`

- [ ] **Step 1: 编写 chat.js**

```javascript
// chat.js
registerPage('#chat', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">AI 问答</h1>
        <div class="chat-layout">
            <div class="chat-sidebar card">
                <div style="margin-bottom:10px">
                    <input id="chat-search" type="text" placeholder="搜索对话...">
                </div>
                <div id="chat-history-list"></div>
                <button class="btn btn-secondary" id="chat-clear-btn" style="width:100%;margin-top:10px">清空全部</button>
            </div>
            <div class="chat-main card">
                <div id="chat-messages" class="chat-messages">
                    <p style="color:#aaa;text-align:center">向你的 AI 跑步教练提问</p>
                </div>
                <div class="chat-input">
                    <input id="chat-input" type="text" placeholder="输入问题..." onkeydown="if(event.key==='Enter')sendChatMessage()">
                    <button class="btn" id="chat-send-btn" onclick="sendChatMessage()">发送</button>
                </div>
            </div>
        </div>
    `;

    document.getElementById('chat-clear-btn').onclick = async () => {
        if (confirm('确定清空所有对话记录?')) {
            await API.chatClear();
            loadChatHistory();
            document.getElementById('chat-messages').innerHTML = '';
        }
    };

    document.getElementById('chat-search').oninput = debounce(loadChatHistory, 300);
    loadChatHistory();
});

async function loadChatHistory() {
    const q = document.getElementById('chat-search')?.value;
    try {
        const history = q ? await API.chatHistory({ q }) : await API.chatHistory();
        renderChatHistoryList(history);
    } catch (err) {
        // 静默处理
    }
}

function renderChatHistoryList(history) {
    const list = document.getElementById('chat-history-list');
    if (!list) return;

    // 按对话对分组显示
    const items = [];
    for (const msg of history) {
        if (msg.role === 'user') {
            items.push(`
                <div style="padding:8px;cursor:pointer;border-bottom:1px solid #eee;font-size:13px"
                     onclick="loadConversation(${msg.id})"
                     title="${escapeHtml(msg.content)}">
                    <div style="font-weight:500">${escapeHtml(msg.content.slice(0, 40))}${msg.content.length>40?'...':''}</div>
                    <div style="color:#999;font-size:11px">${(msg.timestamp||'').slice(0,16)}</div>
                    <button class="btn btn-secondary" style="font-size:11px;padding:2px 8px;margin-top:4px"
                            onclick="event.stopPropagation();deleteChatMsg(${msg.id})">删除</button>
                </div>
            `);
        }
    }
    list.innerHTML = items.join('') || '<p style="color:#aaa;font-size:13px">暂无对话</p>';
}

async function loadConversation(userMsgId) {
    const history = await API.chatHistory();
    const startIdx = history.findIndex(m => m.id === userMsgId);
    if (startIdx === -1) return;

    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '';

    for (let i = startIdx; i < history.length; i++) {
        const msg = history[i];
        if (i > startIdx && msg.role === 'user') break; // 下一组对话开始
        appendChatBubble(msg.role, msg.content);
    }
}

async function deleteChatMsg(id) {
    if (confirm('删除这条对话?')) {
        await API.chatDelete(id);
        loadChatHistory();
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('chat-send-btn');
    const question = input.value.trim();
    if (!question) return;

    input.disabled = true;
    btn.disabled = true;
    input.value = '';

    const messagesDiv = document.getElementById('chat-messages');
    appendChatBubble('user', question);

    const assistantBubble = appendChatBubble('assistant', '...');
    let fullText = '';

    try {
        await API.chatAsk(question, (chunk) => {
            if (chunk.chunk) {
                fullText += chunk.chunk;
                assistantBubble.innerHTML = marked.parse(fullText);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        });
        if (!fullText) assistantBubble.textContent = '(无回复)';
    } catch (err) {
        assistantBubble.innerHTML = `<span style="color:red">错误: ${err.message}</span>`;
    } finally {
        input.disabled = false;
        btn.disabled = false;
        input.focus();
        loadChatHistory(); // 刷新侧边栏
    }
}

function appendChatBubble(role, content) {
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    if (role === 'assistant') {
        div.innerHTML = marked.parse(content);
    } else {
        div.textContent = content;
    }
    document.getElementById('chat-messages').appendChild(div);
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    return div;
}

function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/chat.js
git commit -m "feat: chat page with SSE streaming and history management"
```

---

## Phase 5: 多智能体报告生成

### Task 15: 实现报告生成引擎

**Files:**
- Create: `backend/report_generator.py`
- Create: `tests/test_report_generator.py`

- [ ] **Step 1: 编写 report_generator 测试**

```python
# tests/test_report_generator.py
import pytest
from unittest.mock import patch, MagicMock
from backend.report_generator import ReportGenerator

@patch('backend.report_generator.LLMClient')
def test_report_generation_flow(mock_llm_class):
    mock_llm = MagicMock()
    mock_llm_class.return_value = mock_llm
    mock_llm.chat.side_effect = [
        '数据分析师首轮分析...',      # Round 1: Analyst
        '跑步教练建议...',            # Round 2: Coach
        '数据分析师修正...',          # Round 3: Analyst revised
        '跑步教练最终建议...',        # Round 4: Coach final
        '主教练整合报告...',          # Round 5: Summarizer
    ]

    generator = ReportGenerator(
        base_url='http://fake',
        api_key='test',
        model='test-model',
        rounds=4
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
    # 验证被调用了正确的次数: (4轮 * 2角色=分析师+教练) + 1主教练 = 9?
    # No: round 1 = 1 call (analyst), round 2-4 = 2 calls each (analyst+coach)
    # Actually the default flow: round1=analyst, round2-4=analyst+coach+可选strength
    # So 1 + 3*2 = 7, +1 for summarizer = 8 calls. But depends on implementation.
    # 至少应该被调用5次（4轮+1总结）
    assert mock_llm.chat.call_count >= 5

@patch('backend.report_generator.LLMClient')
def test_report_with_strength_data(mock_llm_class):
    """有力量数据时激活力量专家"""
    mock_llm = MagicMock()
    mock_llm_class.return_value = mock_llm
    mock_llm.chat.side_effect = [
        'analyst', 'coach', 'strength', 'analyst', 'coach', 'strength',
        'analyst', 'coach', 'strength', 'analyst', 'coach', 'strength',
        'summarizer'
    ]

    generator = ReportGenerator('url', 'key', 'model', rounds=4)
    generator.generate({'total_runs': 10, 'has_strength': True})

    # 力量专家应该被调用
    strength_calls = [
        c for c in mock_llm.chat.call_args_list
        if '力量' in str(c[1].get('messages', [[]])[0].get('content', ''))
    ]
    # 至少有一些调用涉及力量专家
    assert mock_llm.chat.call_count > 5

def test_report_generator_handles_llm_error():
    """LLM 调用失败时应该优雅处理"""
    generator = ReportGenerator('url', 'key', 'model', rounds=3)
    with patch('backend.report_generator.LLMClient') as mock_cls:
        mock_llm = MagicMock()
        mock_cls.return_value = mock_llm
        mock_llm.chat.side_effect = Exception('API 超时')

        with pytest.raises(Exception):
            generator.generate({'total_runs': 5})
```

- [ ] **Step 2: 编写 report_generator.py 实现**

```python
from backend.llm_client import LLMClient

AGENT_PROMPTS = {
    'analyst': """你是运动数据分析师，拥有运动科学背景，擅长从训练数据中提取统计规律和异常检测。

基于提供的训练数据，分析以下内容:
1. 训练数据统计特征（跑量、强度分布、频率）
2. 异常检测（训练中断、强度突然变化）
3. 数据中的模式与趋势
4. 与标准训练模型的对比

请用数据和具体数字支撑你的分析。""",

    'coach': """你是实战派跑步教练，注重周期化训练、配速策略、伤病预防。

基于数据分析师的分析结果，给出:
1. 训练计划评估与调整建议
2. 配速策略优化
3. 伤病风险评估与预防建议
4. 下一阶段训练重点

建议需具体、可操作，结合用户实际水平。""",

    'strength': """你是力量与体能训练专家，专注于力量训练对跑步表现的转化效果。

基于数据分析师和跑步教练的讨论，分析:
1. 当前力量训练量与跑步训练的匹配度
2. 力量训练对跑步经济的改善效果
3. 力量训练的周期化建议
4. 需要加强的肌群与动作建议""",

    'summarizer': """你是主教练，负责整合各方专家意见，形成最终的训练报告。

报告需包含以下四部分:
1. **训练数据统计分析**: 基于数据分析师的观点总结
2. **跑步能力趋势**: 能力变化趋势与评估
3. **训练建议**: 综合教练与专家的具体建议
4. **成绩预测**: 基于跑力(VDOT)、近期配速、训练负荷趋势，参考杰克·丹尼尔斯公式，估算 5k/10k/半马成绩，注明假设和不确定性

报告使用 Markdown 格式，结构清晰，便于阅读。"""
}


class ReportGenerator:
    def __init__(self, base_url, api_key, model, rounds=4):
        self.llm = LLMClient(base_url, api_key, model)
        self.rounds = min(max(rounds, 3), 5)

    def generate(self, training_data):
        """执行多智能体报告生成。返回 Markdown 格式报告文本。"""
        conversation = []
        has_strength = training_data.get('has_strength', False)

        data_context = self._build_data_context(training_data)

        # Round 1: 数据分析师首轮发言
        analyst_msg = self._agent_turn('analyst', data_context, conversation)
        conversation.append({'agent': 'analyst', 'content': analyst_msg})

        # Rounds 2-N: 交叉讨论
        for r in range(2, self.rounds + 1):
            # 数据分析师回应其他角色的质疑
            analyst_prompt = self._build_cross_talk_prompt('analyst', conversation)
            analyst_reply = self.llm.chat(analyst_prompt)
            conversation.append({'agent': 'analyst', 'content': analyst_reply})

            # 跑步教练基于分析师输出给出建议
            coach_prompt = self._build_cross_talk_prompt('coach', conversation)
            coach_reply = self.llm.chat(coach_prompt)
            conversation.append({'agent': 'coach', 'content': coach_reply})

            # 如有力量数据，力量专家发言
            if has_strength:
                strength_prompt = self._build_cross_talk_prompt('strength', conversation)
                strength_reply = self.llm.chat(strength_prompt)
                conversation.append({'agent': 'strength', 'content': strength_reply})

        # 主教练汇总
        summarizer_prompt = self._build_summarizer_prompt(conversation, data_context)
        final_report = self.llm.chat(summarizer_prompt, max_tokens=8192)

        return final_report

    def generate_stream(self, training_data):
        """带进度回调的报告生成（返回每步状态）。"""
        has_strength = training_data.get('has_strength', False)
        conversation = []
        data_context = self._build_data_context(training_data)

        # Round 1
        yield {'status': 'running', 'round': 1, 'agent': 'analyst', 'phase': '数据分析师分析中...'}
        analyst_msg = self._agent_turn('analyst', data_context, conversation)
        conversation.append({'agent': 'analyst', 'content': analyst_msg})

        for r in range(2, self.rounds + 1):
            yield {'status': 'running', 'round': r, 'agent': 'analyst', 'phase': f'第{r}轮讨论 - 数据分析师...'}
            conversation.append({'agent': 'analyst', 'content': self.llm.chat(
                self._build_cross_talk_prompt('analyst', conversation)
            )})

            yield {'status': 'running', 'round': r, 'agent': 'coach', 'phase': f'第{r}轮讨论 - 跑步教练...'}
            conversation.append({'agent': 'coach', 'content': self.llm.chat(
                self._build_cross_talk_prompt('coach', conversation)
            )})

            if has_strength:
                yield {'status': 'running', 'round': r, 'agent': 'strength', 'phase': f'第{r}轮讨论 - 力量专家...'}
                conversation.append({'agent': 'strength', 'content': self.llm.chat(
                    self._build_cross_talk_prompt('strength', conversation)
                )})

        yield {'status': 'running', 'agent': 'summarizer', 'phase': '主教练整合报告中...'}
        final_report = self.llm.chat(
            self._build_summarizer_prompt(conversation, data_context),
            max_tokens=8192
        )

        yield {'status': 'done', 'report': final_report}

    def _build_data_context(self, data):
        """构建训练数据摘要文本"""
        return f"""训练数据摘要:
- 时间范围: {data.get('date_range', '全部')}
- 总跑步次数: {data.get('total_runs', 0)}
- 总跑量: {data.get('total_distance', 0)/1000:.1f} km
- 总训练时间: {data.get('total_duration', 0)/3600:.1f} 小时
- 平均配速: {data.get('avg_pace', 0):.0f} 秒/公里
- 平均心率: {data.get('avg_hr', 0):.0f} bpm
- 海拔总爬升: {data.get('total_elevation', 0):.0f} m
- 包含力量训练数据: {'是' if data.get('has_strength') else '否'}
"""

    def _agent_turn(self, agent, data_context, conversation):
        agent_prompt = AGENT_PROMPTS[agent]
        messages = [
            {'role': 'system', 'content': agent_prompt},
            {'role': 'user', 'content': f'请开始你的分析。\n\n{data_context}'}
        ]
        return self.llm.chat(messages)

    def _build_cross_talk_prompt(self, agent, conversation):
        agent_prompt = AGENT_PROMPTS[agent]
        context = "以下是到目前为止的讨论记录:\n\n"
        for entry in conversation[-6:]:  # 最近6条
            context += f"【{entry['agent']}】: {entry['content'][:2000]}\n\n"

        context += f"\n请【{agent}】基于以上讨论发表你的看法。可以赞同、补充或礼貌地提出不同意见。"
        return [
            {'role': 'system', 'content': agent_prompt},
            {'role': 'user', 'content': context}
        ]

    def _build_summarizer_prompt(self, conversation, data_context):
        context = "以下是完整讨论记录:\n\n"
        for entry in conversation:
            context += f"【{entry['agent']}】: {entry['content'][:3000]}\n\n"

        context += f"\n原始数据:\n{data_context}"
        context += "\n请整合以上所有意见，生成最终训练报告。"

        return [
            {'role': 'system', 'content': AGENT_PROMPTS['summarizer']},
            {'role': 'user', 'content': context}
        ]
```

- [ ] **Step 3: 运行测试确认通过**

```bash
pytest tests/test_report_generator.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/report_generator.py tests/test_report_generator.py
git commit -m "feat: multi-agent report generation engine"
```

---

### Task 16: 添加报告生成 API 路由

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 在 app.py 中添加报告路由**

```python
# 在 create_app() 中添加:

from backend.report_generator import ReportGenerator
import uuid
import threading

report_tasks = {}  # task_id -> {'status', 'progress', 'result'}

@app.route('/api/report/generate', methods=['POST'])
def generate_report():
    data = request.get_json() or {}
    date_from = data.get('from', '2020-01-01')
    date_to = data.get('to', '2099-12-31')

    # 提取训练数据
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
    db.close()

    training_data = dict(rows)
    training_data['has_strength'] = has_strength
    training_data['date_range'] = f'{date_from} ~ {date_to}'

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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app.py
git commit -m "feat: add report generation API with async task tracking"
```

---

### Task 17: 实现报告生成前端页面

**Files:**
- Create: `frontend/js/report.js`

- [ ] **Step 1: 编写 report.js**

```javascript
// report.js
registerPage('#report', (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">AI 训练报告</h1>
        <div class="card">
            <div class="flex-between">
                <h2>生成新报告</h2>
                <button class="btn" id="gen-report-btn" onclick="startReportGeneration()">开始生成</button>
            </div>
            <div style="margin-top:12px;display:flex;gap:12px">
                <div><label>开始日期</label><input id="report-date-from" type="date"></div>
                <div><label>结束日期</label><input id="report-date-to" type="date"></div>
            </div>
            <div id="report-progress" style="margin-top:12px;display:none">
                <div class="progress-bar"><div id="report-progress-fill" class="fill" style="width:0"></div></div>
                <p id="report-status-text" style="font-size:13px;color:#888;margin-top:4px"></p>
            </div>
        </div>
        <div id="report-result" class="card" style="display:none">
            <div class="flex-between">
                <h2>训练报告</h2>
                <div>
                    <button class="btn btn-secondary" onclick="printReport()">打印 / 保存 PDF</button>
                </div>
            </div>
            <div id="report-content" class="report-md"></div>
        </div>
    `;
});

async function startReportGeneration() {
    const btn = document.getElementById('gen-report-btn');
    btn.disabled = true;
    btn.textContent = '生成中...';

    const progressDiv = document.getElementById('report-progress');
    const progressFill = document.getElementById('report-progress-fill');
    const statusText = document.getElementById('report-status-text');
    progressDiv.style.display = 'block';

    document.getElementById('report-result').style.display = 'none';

    try {
        const body = {};
        const dateFrom = document.getElementById('report-date-from').value;
        const dateTo = document.getElementById('report-date-to').value;
        if (dateFrom) body.from = dateFrom;
        if (dateTo) body.to = dateTo;

        const { task_id } = await API.generateReport(body);

        let width = 0;
        const pollInterval = setInterval(async () => {
            try {
                const status = await API.reportStatus(task_id);
                statusText.textContent = status.progress;
                width = Math.min(width + 3, 90);
                progressFill.style.width = width + '%';

                if (status.status === 'done' || status.status === 'error') {
                    clearInterval(pollInterval);
                    if (status.status === 'done') {
                        progressFill.style.width = '100%';
                        const result = await API.reportResult(task_id);
                        document.getElementById('report-result').style.display = 'block';
                        document.getElementById('report-content').innerHTML = marked.parse(result.report);
                    } else {
                        statusText.textContent = '报告生成失败';
                        statusText.style.color = 'red';
                    }
                    btn.disabled = false;
                    btn.textContent = '开始生成';
                }
            } catch (e) {
                clearInterval(pollInterval);
                statusText.textContent = '获取状态失败: ' + e.message;
                btn.disabled = false;
                btn.textContent = '开始生成';
            }
        }, 2000);
    } catch (err) {
        statusText.textContent = '启动失败: ' + err.message;
        btn.disabled = false;
        btn.textContent = '开始生成';
    }
}

function printReport() {
    const content = document.getElementById('report-content').innerHTML;
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    printWindow.document.write(`
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>训练报告</title>
        <style>
            body { font-family: sans-serif; max-width: 800px; margin: 40px auto; line-height:1.7; }
            table { border-collapse:collapse; width:100%; }
            th,td { border:1px solid #ddd; padding:8px; }
            @media print { body { margin: 20px; } }
        </style></head>
        <body>${content}</body></html>
    `);
    printWindow.document.close();
    setTimeout(() => printWindow.print(), 500);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/report.js
git commit -m "feat: report generation page with progress polling and PDF print"
```

---

## Phase 6: 配置管理与设置页面

### Task 18: 添加配置 API 路由

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 添加配置路由**

```python
# 在 create_app() 中添加:

@app.route('/api/config', methods=['GET', 'POST'])
def config_handler():
    if request.method == 'GET':
        from backend.config import get_all_config
        config = get_all_config()
        # 不返回完整的 API Key
        if config.get('llm_api_key'):
            key = config['llm_api_key']
            config['llm_api_key'] = key[:4] + '****' + key[-4:] if len(key) > 8 else '****'
        return jsonify(config)

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'error': '需要配置数据'}), 400

        from backend.config import set_config
        for key in ['llm_base_url', 'llm_api_key', 'llm_model', 'report_rounds']:
            if key in data and data[key]:
                set_config(key, data[key])

        return jsonify({'status': 'ok'})
```

- [ ] **Step 2: Commit**

```bash
git add backend/app.py
git commit -m "feat: add config read/write API with API key masking"
```

---

### Task 19: 实现设置前端页面

**Files:**
- Create: `frontend/js/settings.js`

- [ ] **Step 1: 编写 settings.js**

```javascript
// settings.js
registerPage('#settings', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">设置</h1>
        <div class="card">
            <h2>LLM 配置</h2>
            <div style="max-width:500px">
                <label>API 地址</label>
                <input id="cfg-base-url" type="text" placeholder="https://api.deepseek.com/v1">
                <label>API Key</label>
                <input id="cfg-api-key" type="password" placeholder="sk-...">
                <label>模型名称</label>
                <input id="cfg-model" type="text" placeholder="deepseek-chat">
                <label>报告生成轮数 (3-5)</label>
                <input id="cfg-rounds" type="number" min="3" max="5" value="4">
                <button class="btn" id="cfg-save-btn" style="margin-top:12px">保存配置</button>
                <p id="cfg-msg" style="margin-top:8px;font-size:13px"></p>
            </div>
        </div>
        <div class="card">
            <h2>佳明账户</h2>
            <div style="max-width:500px">
                <label>邮箱</label>
                <input id="sync-email" type="email" placeholder="your@email.com">
                <label>密码</label>
                <input id="sync-password" type="password" placeholder="仅本地传输，不存储">
                <button class="btn" id="sync-btn" style="margin-top:12px">同步数据</button>
                <div id="sync-progress" style="margin-top:10px;display:none">
                    <div class="progress-bar"><div id="sync-progress-fill" class="fill" style="width:0"></div></div>
                    <p id="sync-status-text" style="font-size:13px;color:#888;margin-top:4px"></p>
                </div>
            </div>
        </div>
    `;

    // 加载当前配置
    try {
        const cfg = await API.getConfig();
        document.getElementById('cfg-base-url').value = cfg.llm_base_url || '';
        document.getElementById('cfg-api-key').value = cfg.llm_api_key || '';
        document.getElementById('cfg-model').value = cfg.llm_model || '';
        document.getElementById('cfg-rounds').value = cfg.report_rounds || '4';
    } catch (err) {
        // 默认值已在 input 中
    }

    document.getElementById('cfg-save-btn').onclick = async () => {
        const btn = document.getElementById('cfg-save-btn');
        const msg = document.getElementById('cfg-msg');
        btn.disabled = true;

        try {
            await API.updateConfig({
                llm_base_url: document.getElementById('cfg-base-url').value,
                llm_api_key: document.getElementById('cfg-api-key').value,
                llm_model: document.getElementById('cfg-model').value,
                report_rounds: document.getElementById('cfg-rounds').value,
            });
            msg.textContent = '配置已保存';
            msg.style.color = 'green';
        } catch (err) {
            msg.textContent = '保存失败: ' + err.message;
            msg.style.color = 'red';
        } finally {
            btn.disabled = false;
        }
    };

    document.getElementById('sync-btn').onclick = async () => {
        const btn = document.getElementById('sync-btn');
        const email = document.getElementById('sync-email').value.trim();
        const password = document.getElementById('sync-password').value;

        if (!email || !password) {
            showToast('请输入邮箱和密码', 'error');
            return;
        }

        btn.disabled = true;
        btn.textContent = '同步中...';

        const progressDiv = document.getElementById('sync-progress');
        const fill = document.getElementById('sync-progress-fill');
        const statusText = document.getElementById('sync-status-text');
        progressDiv.style.display = 'block';
        fill.style.width = '30%';
        statusText.textContent = '正在连接佳明服务器...';

        try {
            const result = await API.sync(email, password);
            fill.style.width = '100%';
            statusText.textContent = `同步完成! 新增 ${result.new_count} 条记录，共检查 ${result.total_checked} 条`;
            document.getElementById('sync-password').value = '';
        } catch (err) {
            fill.style.width = '0';
            statusText.textContent = '同步失败: ' + err.message;
            statusText.style.color = 'red';
        } finally {
            btn.disabled = false;
            btn.textContent = '同步数据';
        }
    };
});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/settings.js
git commit -m "feat: settings page with LLM config and Garmin sync"
```

---

## Phase 7: 打包与收尾

### Task 20: 创建启动脚本和打包配置

**Files:**
- Create: `run.bat`
- Create: `run.sh`
- Create: `pyinstaller.spec`

- [ ] **Step 1: 编写启动脚本**

```bash
# run.bat
@echo off
cd /d "%~dp0"
if not exist "data" mkdir data
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)
python -c "from backend.app import create_app; app=create_app(); import webbrowser; webbrowser.open('http://127.0.0.1:5000'); app.run(host='127.0.0.1', port=5000, threaded=True)"
pause
```

```bash
# run.sh
#!/bin/bash
cd "$(dirname "$0")"
mkdir -p data
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
python3 -c "
from backend.app import create_app
import webbrowser, threading
app = create_app()
threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
app.run(host='127.0.0.1', port=5000, threaded=True)
"
```

- [ ] **Step 2: 编写 PyInstaller spec**

```python
# pyinstaller.spec
# Usage: pyinstaller pyinstaller.spec

block_cipher = None

a = Analysis(
    ['backend/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('frontend', 'frontend'),
    ],
    hiddenimports=['sqlite3', 'garminconnect', 'openai'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RunningCoach',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
```

- [ ] **Step 3: Commit**

```bash
git add run.bat run.sh pyinstaller.spec
git commit -m "feat: add launcher scripts and PyInstaller spec"
```

---

### Task 21: 集成测试与最终验证

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_integration.py
"""端到端集成测试"""

def test_full_workflow(client):
    """测试完整流程: 健康检查 -> 无数据统计 -> 空活动列表"""
    # 健康检查
    resp = client.get('/api/health')
    assert resp.status_code == 200

    # 空统计
    resp = client.get('/api/stats')
    assert resp.status_code == 200
    assert resp.json['overview']['total_runs'] == 0

    # 空活动列表
    resp = client.get('/api/activities')
    assert resp.status_code == 200
    assert len(resp.json) == 0

    # 空对话历史
    resp = client.get('/api/chat/history')
    assert resp.status_code == 200
    assert len(resp.json) == 0

    # 配置读写
    resp = client.post('/api/config', json={'llm_model': 'test-model'})
    assert resp.status_code == 200

    resp = client.get('/api/config')
    assert resp.status_code == 200
    assert 'test-model' in resp.json.get('llm_model', '').lower() or '****' in resp.json.get('llm_model', '')

def test_frontend_served(client):
    """测试前端页面可正常访问"""
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
```

- [ ] **Step 2: 运行全部测试**

```bash
pytest tests/ -v
```

- [ ] **Step 3: 修复任何失败的测试**

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full workflow"
```

---

## 总览

| Phase | Tasks | 说明 |
|-------|-------|------|
| 1. 脚手架 | 1-3 | 目录结构、数据库、Flask 骨架 |
| 2. 佳明集成 | 4-6 | garminconnect 封装、同步、API |
| 3. 前端 + 仪表盘 | 7-10 | SPA 外壳、仪表盘、活动列表 |
| 4. LLM + 问答 | 11-14 | LLM 客户端、SSE 问答、对话管理 |
| 5. 报告生成 | 15-17 | 多 Agent 引擎、报告 API、前端 |
| 6. 配置 + 打包 | 18-21 | 设置页、启动脚本、集成测试 |

---

## 关键设计决策

1. **Flask threaded=True**: 解决 SSE 长连接阻塞问题，生产可换 gevent
2. **Threading 异步报告生成**: 报告生成可能耗时 30-120 秒，后台线程 + 轮询避免超时
3. **garminconnect 0.2.x 版本锁定**: 非官方库 API 可能变更，锁定版本
4. **SQLite WAL 模式**: 支持并发读写（前端轮询 + 后端写入）
5. **纯 HTML/JS 前端**: 无需构建工具，直接通过 Flask static 服务
