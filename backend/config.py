from backend.database import get_db

DEFAULT_CONFIG = {
    'llm_base_url': 'https://api.deepseek.com/v1',
    'llm_api_key': '',
    'llm_model': 'deepseek-chat',
    'report_rounds': '4',
    'sync_strength': 'true',
    'sync_auto_interval': '0',
    'profile_age': '',
    'profile_gender': '',
    'profile_height': '',
    'profile_weight': '',
    'profile_resting_hr': '',
    'profile_max_hr': '',
    'profile_race_goal': '',
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
