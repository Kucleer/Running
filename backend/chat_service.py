from backend.database import get_db
import uuid

SYSTEM_PROMPT = """你是私人跑步教练，可根据用户提供的训练数据给出个性化建议。

你具备运动科学背景，注重周期化训练、配速策略、伤病预防。
回答时:
1. 引用数据中的具体数字支撑观点
2. 给出可操作的训练建议
3. 指出潜在风险
4. 鼓励但不盲目乐观

{profile_info}
训练数据摘要:
{training_summary}

近期训练记录（逐条）:
{recent_activities}
"""


class ChatService:
    def create_session(self, title=''):
        session_id = str(uuid.uuid4())[:12]
        db = get_db()
        db.execute(
            "INSERT INTO chat_sessions (id, title) VALUES (?, ?)",
            (session_id, title or '新对话')
        )
        db.commit()
        db.close()
        return session_id

    def get_sessions(self):
        db = get_db()
        rows = db.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM chat_history WHERE session_id=s.id) as msg_count "
            "FROM chat_sessions s ORDER BY s.created_at DESC"
        ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def delete_session(self, session_id):
        db = get_db()
        db.execute("DELETE FROM chat_history WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
        db.commit()
        db.close()

    def build_messages(self, session_id, question, training_summary, recent_history,
                       recent_activities='', profile_info=''):
        system_content = SYSTEM_PROMPT.format(
            profile_info=profile_info,
            training_summary=training_summary or '暂无训练数据',
            recent_activities=recent_activities or '暂无'
        )

        messages = [{'role': 'system', 'content': system_content}]

        for entry in recent_history[-10:]:
            messages.append({'role': entry['role'], 'content': entry['content']})

        messages.append({'role': 'user', 'content': question})
        return messages

    def save_message(self, session_id, role, content, context_snapshot=''):
        db = get_db()
        db.execute(
            "INSERT INTO chat_history (session_id, role, content, context_snapshot) VALUES (?, ?, ?, ?)",
            (session_id, role, content, context_snapshot)
        )
        # Update session title from first user message
        if role == 'user':
            title = content[:40] + ('...' if len(content) > 40 else '')
            db.execute(
                "UPDATE chat_sessions SET title=? WHERE id=? AND title='新对话'",
                (title, session_id)
            )
        db.commit()
        db.close()

    def get_history(self, session_id=None, limit=100):
        db = get_db()
        if session_id:
            rows = db.execute(
                "SELECT * FROM chat_history WHERE session_id=? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM chat_history WHERE session_id='' ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        db.close()
        return [dict(r) for r in (rows if session_id else reversed(rows))]

    def search_history(self, keyword):
        db = get_db()
        rows = db.execute(
            "SELECT * FROM chat_history WHERE content LIKE ? ORDER BY timestamp DESC",
            (f'%{keyword}%',)
        ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def delete_message(self, msg_id):
        db = get_db()
        db.execute("DELETE FROM chat_history WHERE id=?", (msg_id,))
        db.commit()
        db.close()

    def clear_all(self):
        db = get_db()
        db.execute("DELETE FROM chat_history")
        db.execute("DELETE FROM chat_sessions")
        db.commit()
        db.close()
