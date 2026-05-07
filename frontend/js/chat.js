let currentSessionId = '';

registerPage('#chat', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">AI 问答</h1>
        <div class="chat-layout">
            <div class="chat-sidebar card">
                <div style="margin-bottom:10px">
                    <button class="btn" id="chat-new-session-btn" style="width:100%;margin-bottom:8px">+ 新对话</button>
                    <input id="chat-search" type="text" placeholder="搜索对话...">
                </div>
                <div id="chat-session-list"></div>
                <button class="btn btn-secondary" id="chat-clear-btn" style="width:100%;margin-top:10px">清空全部</button>
            </div>
            <div class="chat-main card">
                <div id="chat-messages" class="chat-messages">
                    <p style="color:var(--text-muted);text-align:center;padding-top:40px">选择一个对话或创建新对话</p>
                </div>
                <div class="chat-input" id="chat-input-area" style="display:none">
                    <input id="chat-input" type="text" placeholder="输入问题..." onkeydown="if(event.key==='Enter')sendChatMessage()">
                    <button class="btn" id="chat-send-btn" onclick="sendChatMessage()">发送</button>
                </div>
            </div>
        </div>
    `;

    document.getElementById('chat-new-session-btn').onclick = newSession;
    document.getElementById('chat-clear-btn').onclick = async () => {
        if (confirm('确定清空所有对话?')) {
            await API.chatClear();
            currentSessionId = '';
            document.getElementById('chat-messages').innerHTML = '<p style="color:var(--text-muted);text-align:center;padding-top:40px">选择一个对话或创建新对话</p>';
            document.getElementById('chat-input-area').style.display = 'none';
            loadSessions();
        }
    };
    document.getElementById('chat-search').oninput = debounce(loadSessions, 300);
    loadSessions();
});

async function newSession() {
    const { session_id } = await API.chatCreateSession();
    currentSessionId = session_id;
    document.getElementById('chat-messages').innerHTML = '<p style="color:#aaa;text-align:center">开始新的对话</p>';
    document.getElementById('chat-input-area').style.display = 'flex';
    document.getElementById('chat-input').focus();
    loadSessions();
}

async function loadSessions() {
    const q = document.getElementById('chat-search')?.value;
    try {
        const sessions = await API.chatSessions();
        const filtered = q ? sessions.filter(s => s.title.includes(q)) : sessions;
        renderSessionList(filtered);
    } catch (err) {
    }
}

function renderSessionList(sessions) {
    const list = document.getElementById('chat-session-list');
    if (!list) return;
    if (!sessions.length) {
        list.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px">暂无对话</p>';
        return;
    }
    list.innerHTML = sessions.map(s => `
        <div class="session-item${s.id===currentSessionId?' active':''}"
             onclick="openSession('${s.id}')">
            <div style="font-weight:500;display:flex;justify-content:space-between">
                <span>${escapeHtml(s.title)}</span>
                <span style="color:var(--text-muted);font-size:11px">${s.msg_count||0}</span>
            </div>
            <div style="color:var(--text-muted);font-size:11px;margin-top:2px">${(s.created_at||'').slice(0,16)}</div>
            <button class="btn btn-secondary btn-sm" style="margin-top:4px"
                    onclick="event.stopPropagation();deleteSession('${s.id}')">删除</button>
        </div>
    `).join('');
}

async function openSession(sessionId) {
    currentSessionId = sessionId;
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '<p style="color:var(--text-muted);padding-top:40px;text-align:center">加载中...</p>';
    document.getElementById('chat-input-area').style.display = 'flex';

    try {
        const history = await API.chatHistory({ session_id: sessionId });
        messagesDiv.innerHTML = '';
        for (const msg of history) {
            appendChatBubble(msg.role, msg.content);
        }
        if (!history.length) {
            messagesDiv.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding-top:40px">开始新的对话</p>';
        }
    } catch (err) {
        messagesDiv.innerHTML = `<p style="color:var(--primary);text-align:center">加载失败: ${err.message}</p>`;
    }
    loadSessions();
}

async function deleteSession(sessionId) {
    if (!confirm('确定删除这个对话?')) return;
    await API.chatDeleteSession(sessionId);
    if (currentSessionId === sessionId) {
        currentSessionId = '';
        document.getElementById('chat-messages').innerHTML = '<p style="color:var(--text-muted);text-align:center;padding-top:40px">选择一个对话或创建新对话</p>';
        document.getElementById('chat-input-area').style.display = 'none';
    }
    loadSessions();
}

async function sendChatMessage() {
    if (!currentSessionId) {
        await newSession();
    }
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
        await API.chatAsk(question, currentSessionId, (chunk) => {
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
        loadSessions();
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
    document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
    return div;
}

function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
