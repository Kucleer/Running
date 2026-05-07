import pytest
import os
from backend.chat_service import ChatService


def test_build_context():
    service = ChatService()
    summary = "最近12周跑量: 150km, 平均配速: 5:30"
    messages = service.build_messages('sess1', '我今天该跑什么?', summary, [])
    assert len(messages) == 2
    assert messages[0]['role'] == 'system'
    assert '私人跑步教练' in messages[0]['content']
    assert '150km' in messages[0]['content']
    assert messages[1]['role'] == 'user'


def test_save_and_get_history(test_db_path):
    from backend.database import init_db, get_db, set_db_path
    set_db_path(test_db_path)
    init_db()

    service = ChatService()
    sid = service.create_session('Test')
    service.save_message(sid, 'user', '问题1')
    service.save_message(sid, 'assistant', '回答1')

    history = service.get_history(session_id=sid)
    assert len(history) == 2

    results = service.search_history('问题1')
    assert len(results) == 1


def test_delete_history(test_db_path):
    from backend.database import init_db, set_db_path
    set_db_path(test_db_path)
    init_db()

    service = ChatService()
    sid = service.create_session('Test')
    service.save_message(sid, 'user', '问题X')
    history = service.get_history(session_id=sid)
    assert len(history) == 1

    service.delete_message(history[0]['id'])
    assert len(service.get_history(session_id=sid)) == 0


def test_clear_history(test_db_path):
    from backend.database import init_db, set_db_path
    set_db_path(test_db_path)
    init_db()

    service = ChatService()
    sid = service.create_session('Test')
    service.save_message(sid, 'user', 'Q1')
    service.save_message(sid, 'assistant', 'A1')
    assert len(service.get_history(session_id=sid)) == 2

    service.clear_all()
    assert len(service.get_history(session_id=sid)) == 0
    assert len(service.get_sessions()) == 0


def test_session_isolation(test_db_path):
    from backend.database import init_db, set_db_path
    set_db_path(test_db_path)
    init_db()

    service = ChatService()
    sid1 = service.create_session('Session 1')
    sid2 = service.create_session('Session 2')

    service.save_message(sid1, 'user', 'Q1')
    service.save_message(sid1, 'assistant', 'A1')
    service.save_message(sid2, 'user', 'Q2')
    service.save_message(sid2, 'assistant', 'A2')

    h1 = service.get_history(session_id=sid1)
    h2 = service.get_history(session_id=sid2)
    assert len(h1) == 2
    assert len(h2) == 2
    assert h1[0]['content'] == 'Q1'
    assert h2[0]['content'] == 'Q2'

    sessions = service.get_sessions()
    assert len(sessions) == 2

    service.delete_session(sid1)
    assert len(service.get_history(session_id=sid1)) == 0
    assert len(service.get_sessions()) == 1
