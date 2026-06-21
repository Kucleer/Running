import pytest

from backend.database import get_db, init_db, set_db_path
from backend.pace_distribution import get_pace_distribution


def test_pace_distribution_uses_activity_splits(test_db_path):
    set_db_path(test_db_path)
    init_db()
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance, avg_pace)
        VALUES
        (1, 'Best 5K', 'running', '2026-06-01 07:00:00', 1500, 5000, 300),
        (2, 'Split Run', 'running', '2026-06-02 07:00:00', 1800, 5000, 360)
    """)
    db.execute("""
        INSERT INTO activity_splits
            (activity_id, split_index, source, distance, duration, avg_pace)
        VALUES
            (2, 1, 'test', 2500, 750, 300),
            (2, 2, 'test', 2500, 1050, 420)
    """)
    db.commit()

    dist = get_pace_distribution(db, '2026-06-01', '2026-06-30 23:59:59')
    db.close()

    assert round(sum(row['count'] for row in dist), 1) == 10.0
    assert len(dist) == 5
    assert any(row['count'] == pytest.approx(2.5) for row in dist)


def test_pace_distribution_fallback_without_vdot(test_db_path):
    set_db_path(test_db_path)
    init_db()
    db = get_db()
    db.execute("""
        INSERT INTO activities (id, name, type, start_time, duration, distance, avg_pace)
        VALUES
        (1, 'Short Run', 'running', '2026-06-01 07:00:00', 1200, 3000, 400),
        (2, 'Easy Run', 'running', '2026-06-02 07:00:00', 1764, 4900, 360)
    """)
    db.commit()

    dist = get_pace_distribution(db, '2026-06-01', '2026-06-30 23:59:59')
    db.close()

    assert dist == [{'pace_range': '6:00-7:00', 'count': 7.9}]
