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
    assert 'reports' in table_names


def test_init_db_idempotent(test_db_path):
    os.environ['RUNNING_DB_PATH'] = test_db_path
    init_db()
    init_db()
