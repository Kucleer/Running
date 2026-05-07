registerPage('#activities', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">运动记录</h1>
        <div id="act-detail" style="display:none"></div>
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
    `;

    document.getElementById('act-filter-btn').onclick = () => loadActivities(container);
    loadActivities(container);
});

async function loadActivities(container) {
    const params = {};
    const typeVal = document.getElementById('act-type-filter').value;
    const qVal = document.getElementById('act-search').value;
    const fromVal = document.getElementById('act-date-from').value;
    const toVal = document.getElementById('act-date-to').value;
    if (typeVal) params.type = typeVal;
    if (qVal) params.q = qVal;
    if (fromVal) params.from = fromVal;
    if (toVal) params.to = toVal;

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

        const compactCard = 'padding:10px 12px';
        const compactValue = 'font-size:20px';
        const compactLabel = 'font-size:11px';
        const u = 'style="font-size:10px;color:#999"';

        // Basic metrics
        const basicItems = [];
        basicItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${(act.distance/1000).toFixed(2)}<span ${u}> km</span></div><div class="label" style="${compactLabel}">距离</div></div>`);
        basicItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${formatDuration(act.duration)}</div><div class="label" style="${compactLabel}">时长</div></div>`);
        basicItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${formatPace(act.avg_pace)}<span ${u}> /km</span></div><div class="label" style="${compactLabel}">平均配速</div></div>`);
        basicItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.avg_heart_rate) || '-'}<span ${u}> bpm</span></div><div class="label" style="${compactLabel}">平均心率</div></div>`);
        basicItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.max_heart_rate) || '-'}<span ${u}> bpm</span></div><div class="label" style="${compactLabel}">最大心率</div></div>`);
        basicItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${act.elevation_gain || 0}<span ${u}> m</span></div><div class="label" style="${compactLabel}">海拔爬升</div></div>`);

        // Running dynamics
        const dynItems = [];
        if (act.avg_cadence) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.avg_cadence)}<span ${u}> spm</span></div><div class="label" style="${compactLabel}">平均步频</div></div>`);
        if (act.max_cadence) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.max_cadence)}<span ${u}> spm</span></div><div class="label" style="${compactLabel}">最高步频</div></div>`);
        if (act.avg_ground_contact_time) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.avg_ground_contact_time)}<span ${u}> ms</span></div><div class="label" style="${compactLabel}">触地时间</div></div>`);
        if (act.avg_vertical_oscillation) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${(act.avg_vertical_oscillation).toFixed(1)}<span ${u}> cm</span></div><div class="label" style="${compactLabel}">垂直振幅</div></div>`);
        if (act.avg_stride_length) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${(act.avg_stride_length/100).toFixed(2)}<span ${u}> m</span></div><div class="label" style="${compactLabel}">步幅</div></div>`);
        if (act.training_effect) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${act.training_effect.toFixed(1)}</div><div class="label" style="${compactLabel}">训练效果</div></div>`);
        if (act.vo2max) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.vo2max)}</div><div class="label" style="${compactLabel}">VO2max</div></div>`);
        if (act.lactate_threshold) dynItems.push(`<div class="stat-card" style="${compactCard}"><div class="value" style="${compactValue}">${Math.round(act.lactate_threshold)}<span ${u}> bpm</span></div><div class="label" style="${compactLabel}">乳酸阈值</div></div>`);

        const dynamicsHtml = dynItems.length ? `
            <div>
                <h3 style="margin-bottom:8px;font-size:13px">跑步动态</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">${dynItems.join('')}</div>
            </div>` : '';

        detail.innerHTML = `
            <div class="card" style="padding:18px 20px">
                <div class="flex-between">
                    <h2>${escapeHtml(act.name)}</h2>
                    <button class="btn btn-secondary btn-sm" onclick="document.getElementById('act-detail').style.display='none'">关闭</button>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px">
                    <div>
                        <h3 style="margin-bottom:8px;font-size:13px">基础指标</h3>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">${basicItems.join('')}</div>
                    </div>
                    ${dynamicsHtml}
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
    setTimeout(() => {
        toast.classList.add('out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
