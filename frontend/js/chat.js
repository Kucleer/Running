let currentSessionId = localStorage.getItem('chatSessionId') || '';

registerPage('#chat', async (container) => {
    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">AI Coach</div>
                <h1>AI 问答</h1>
            </div>
            <div class="page-tools">
                <input class="search-input" id="chat-search" type="text" placeholder="搜索对话">
            </div>
        </div>
        <div class="chat-layout">
            <div class="chat-sidebar card">
                <button class="btn" id="chat-new-session-btn" style="width:100%;margin-bottom:10px">新对话</button>
                <div id="chat-session-list" class="chat-session-list"></div>
                <button class="btn btn-secondary" id="chat-clear-btn" style="width:100%;margin-top:10px">清空全部</button>
            </div>
            <div class="chat-main card">
                <div id="chat-messages" class="chat-messages">
                    <div class="empty-state">选择一个对话，或创建新的训练问答。</div>
                </div>
                <div class="chat-input" id="chat-input-area" style="display:none">
                    <label class="chat-options">
                        <input type="checkbox" id="chat-include-strength"> 包含力量训练
                    </label>
                    <div class="chat-compose">
                        <textarea id="chat-input" placeholder="输入你的训练问题..." rows="3" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChatMessage()}"></textarea>
                        <button class="btn" id="chat-send-btn" onclick="sendChatMessage()">发送</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('chat-new-session-btn').onclick = newSession;
    document.getElementById('chat-clear-btn').onclick = async () => {
        if (confirm('确定清空所有对话？')) {
            await API.chatClear();
            currentSessionId = '';
            localStorage.removeItem('chatSessionId');
            resetChatEmpty();
            loadSessions();
        }
    };
    document.getElementById('chat-search').oninput = debounce(loadSessions, 300);
    const sessions = await loadSessions();

    // Restore only sessions that still exist in the backend. A stale local id can
    // otherwise send messages into chat_history without a visible session row.
    if (currentSessionId && sessions.some(s => s.id === currentSessionId)) {
        openSession(currentSessionId);
    } else if (currentSessionId) {
        currentSessionId = '';
        localStorage.removeItem('chatSessionId');
        resetChatEmpty();
    }
});

async function newSession() {
    const { session_id } = await API.chatCreateSession();
    currentSessionId = session_id;
    localStorage.setItem('chatSessionId', session_id);
    document.getElementById('chat-messages').innerHTML = '<div class="empty-state">开始新的对话</div>';
    document.getElementById('chat-input-area').style.display = 'block';
    document.getElementById('chat-input').focus();
    loadSessions();
}

async function loadSessions() {
    const q = document.getElementById('chat-search')?.value;
    try {
        const sessions = await API.chatSessions();
        const filtered = q ? sessions.filter(s => s.title.includes(q)) : sessions;
        renderSessionList(filtered);
        return sessions;
    } catch (err) {
        return [];
    }
}

function renderSessionList(sessions) {
    const list = document.getElementById('chat-session-list');
    if (!list) return;
    if (!sessions.length) {
        list.innerHTML = '<div class="empty-state">暂无对话</div>';
        return;
    }
    list.innerHTML = sessions.map(s => `
        <div class="session-item${s.id === currentSessionId ? ' active' : ''}" onclick="openSession('${s.id}')">
            <div class="session-title-row">
                <span>${escapeHtml(s.title)}</span>
                <span class="muted small">${s.msg_count || 0}</span>
            </div>
            <div class="session-meta">${(s.created_at || '').slice(0, 16)}</div>
            <button class="btn btn-secondary btn-sm" style="margin-top:6px" onclick="event.stopPropagation();deleteSession('${s.id}')">删除</button>
        </div>
    `).join('');
}

async function openSession(sessionId) {
    currentSessionId = sessionId;
    localStorage.setItem('chatSessionId', sessionId);
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '<div class="empty-state">加载中...</div>';
    document.getElementById('chat-input-area').style.display = 'block';

    try {
        const history = await API.chatHistory({ session_id: sessionId });
        messagesDiv.innerHTML = '';
        for (const msg of history) appendChatBubble(msg.role, msg.content);
        if (!history.length) messagesDiv.innerHTML = '<div class="empty-state">开始新的对话</div>';
    } catch (err) {
        messagesDiv.innerHTML = `<div class="empty-state error-text">加载失败：${err.message}</div>`;
    }
    loadSessions();
}

async function deleteSession(sessionId) {
    if (!confirm('确定删除这个对话？')) return;
    await API.chatDeleteSession(sessionId);
    if (currentSessionId === sessionId) {
        currentSessionId = '';
        localStorage.removeItem('chatSessionId');
        resetChatEmpty();
    }
    loadSessions();
}

function resetChatEmpty() {
    document.getElementById('chat-messages').innerHTML = '<div class="empty-state">选择一个对话，或创建新的训练问答。</div>';
    document.getElementById('chat-input-area').style.display = 'none';
}

async function sendChatMessage() {
    if (!currentSessionId) await newSession();
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('chat-send-btn');
    const question = input.value.trim();
    if (!question) return;

    const includeStrength = document.getElementById('chat-include-strength').checked;
    input.disabled = true;
    btn.disabled = true;
    input.value = '';

    const messagesDiv = document.getElementById('chat-messages');
    if (messagesDiv.querySelector('.empty-state')) messagesDiv.innerHTML = '';
    appendChatBubble('user', question);

    const assistantBubble = appendChatBubble('assistant', '...');
    let fullText = '';

    try {
        await API.chatAsk(question, currentSessionId, (chunk) => {
            if (chunk.error) {
                throw new Error(chunk.error);
            }
            if (chunk.chunk) {
                fullText += chunk.chunk;
                assistantBubble.innerHTML = marked.parse(fullText);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }, includeStrength);
        if (!fullText) assistantBubble.textContent = '(无回复)';
    } catch (err) {
        assistantBubble.innerHTML = `<span class="error-text">错误：${err.message}</span>`;
    } finally {
        input.disabled = false;
        btn.disabled = false;
        input.focus();
        loadSessions();
    }
}

function appendChatBubble(role, content) {
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    if (role === 'assistant') div.innerHTML = marked.parse(content);
    else div.textContent = content;
    const messages = document.getElementById('chat-messages');
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
