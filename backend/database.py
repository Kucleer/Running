import sqlite3
import os

DB_PATH = None
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _get_db_path():
    if DB_PATH:
        return DB_PATH
    path = os.environ.get('RUNNING_DB_PATH', os.path.join(_BASE_DIR, '..', 'data', 'running.db'))
    return os.path.abspath(path)


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
            raw_json TEXT,
            avg_cadence REAL,
            max_cadence REAL,
            avg_ground_contact_time REAL,
            avg_vertical_oscillation REAL,
            avg_stride_length REAL,
            training_effect REAL,
            vo2max REAL,
            lactate_threshold REAL,
            detail_json TEXT
        );

        CREATE TABLE IF NOT EXISTS health_data (
            date TEXT PRIMARY KEY,
            hrv_status TEXT,
            hrv_avg REAL,
            sleep_score INTEGER,
            sleep_duration REAL,
            resting_hr REAL,
            body_battery_max INTEGER,
            body_battery_min INTEGER,
            avg_stress REAL,
            training_status TEXT,
            vo2max REAL,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now','localtime')),
            role TEXT,
            content TEXT,
            context_snapshot TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            date_from TEXT,
            date_to TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            content TEXT
        );
    """)
    # Migration: add columns that may not exist on older databases
    _migrate(db, "chat_history", "session_id", "TEXT NOT NULL DEFAULT ''")
    for col, col_def in [
        ("avg_cadence", "REAL"),
        ("max_cadence", "REAL"),
        ("avg_ground_contact_time", "REAL"),
        ("avg_vertical_oscillation", "REAL"),
        ("avg_stride_length", "REAL"),
        ("training_effect", "REAL"),
        ("vo2max", "REAL"),
        ("lactate_threshold", "REAL"),
        ("detail_json", "TEXT"),
    ]:
        _migrate(db, "activities", col, col_def)
    db.commit()
    db.close()


def _migrate(db, table, column, col_def):
    """Add column if it doesn't exist (safe migration)."""
    cols = [r['name'] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
