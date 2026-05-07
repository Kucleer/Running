import pytest
import os
import tempfile


@pytest.fixture
def test_db_path():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    for suffix in ['', '-wal', '-shm']:
        p = path + suffix
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


@pytest.fixture
def app(test_db_path):
    os.environ['RUNNING_DB_PATH'] = test_db_path
    from backend.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()
