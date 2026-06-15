registerPage('#activities', async (container) => {
    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">Activities</div>
                <h1>运动记录</h1>
            </div>
            <div class="page-tools">
                <select id="act-type-filter">
                    <option value="">全部类型</option>
                    <option value="running">跑步</option>
                    <option value="strength_training">力量训练</option>
                    <option value="cycling">骑行</option>
                    <option value="swimming">游泳</option>
                    <option value="other">其他</option>
                </select>
                <input class="search-input" id="act-search" type="text" placeholder="搜索活动名称">
                <input id="act-date-from" type="date">
                <input id="act-date-to" type="date">
                <button class="btn" id="act-filter-btn">筛选</button>
            </div>
        </div>
        <div id="act-detail" style="display:none"></div>
        <div id="act-list"></div>
    `;

    const pendingSearch = sessionStorage.getItem('activitySearch');
    if (pendingSearch) {
        document.getElementById('act-search').value = pendingSearch;
        sessionStorage.removeItem('activitySearch');
    }

    document.getElementById('act-filter-btn').onclick = loadActivities;
    loadActivities();
});

async function loadActivities() {
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
        renderActivityList(await API.activities(params));
    } catch (err) {
        document.getElementById('act-list').innerHTML = `<div class="empty-state error-text">加载失败：${err.message}</div>`;
    }
}

function renderActivityList(activities) {
    const list = document.getElementById('act-list');
    if (!activities.length) {
        list.innerHTML = '<div class="empty-state">暂无运动记录，请先在设置页同步 Garmin 数据。</div>';
        return;
    }

    list.innerHTML = `
        <div class="card">
            <div class="section-title">
                <h2>活动列表</h2>
                <span class="muted small">${activities.length} 条记录</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr>
                        <th>日期</th><th>名称</th><th>类型</th><th>距离</th><th>时长</th><th>配速</th><th>心率</th>
                    </tr></thead>
                    <tbody>
                        ${activities.map(a => `
                            <tr class="row-clickable" onclick="viewActivityDetail(${a.id})">
                                <td>${formatDateTime(a.start_time, false)}</td>
                                <td>${escapeHtml(a.name)}</td>
                                <td>${typeLabel(a.type)}</td>
                                <td>${a.distance ? (a.distance / 1000).toFixed(2) + ' km' : '-'}</td>
                                <td>${formatDuration(a.duration)}</td>
                                <td>${formatPace(a.avg_pace)}</td>
                                <td>${roundOrDash(a.avg_heart_rate)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

async function viewActivityDetail(id) {
    const detail = document.getElementById('act-detail');
    detail.style.display = 'block';
    detail.innerHTML = '<div class="card activity-detail-card"><div class="empty-state">正在加载活动详情...</div></div>';

    try {
        const [act, splits] = await Promise.all([
            API.activityDetail(id),
            API.activitySplits(id).catch(() => [])
        ]);

        const u = value => `<span class="metric-unit">${value}</span>`;
        const metric = (value, label, icon) => `
            <div class="stat-card">
                <div class="metric-icon" data-icon="${icon}">${iconSvg(icon)}</div>
                <div class="value">${value}</div>
                <div class="label">${label}</div>
            </div>
        `;

        const basicItems = [
            metric(`${safeKm(act.distance)} ${u('km')}`, '距离', 'route'),
            metric(formatDuration(act.duration), '用时', 'clock'),
            metric(`${formatPace(act.avg_pace)} ${u('/km')}`, '平均配速', 'timer'),
            metric(`${roundOrDash(act.avg_heart_rate)} ${u('bpm')}`, '平均心率', 'heart'),
            metric(`${roundOrDash(act.max_heart_rate)} ${u('bpm')}`, '最高心率', 'pulse'),
            metric(`${Math.round(act.elevation_gain || 0)} ${u('m')}`, '爬升', 'mountain')
        ];

        const dynItems = [];
        if (act.avg_cadence) dynItems.push(metric(`${Math.round(act.avg_cadence)} ${u('spm')}`, '平均步频', 'steps'));
        if (act.max_cadence) dynItems.push(metric(`${Math.round(act.max_cadence)} ${u('spm')}`, '最高步频', 'speed'));
        if (act.avg_ground_contact_time) dynItems.push(metric(`${Math.round(act.avg_ground_contact_time)} ${u('ms')}`, '触地时间', 'foot'));
        if (act.avg_vertical_oscillation) dynItems.push(metric(`${act.avg_vertical_oscillation.toFixed(1)} ${u('cm')}`, '垂直振幅', 'wave'));
        if (act.avg_stride_length) dynItems.push(metric(`${(act.avg_stride_length / 100).toFixed(2)} ${u('m')}`, '步幅', 'stride'));
        if (act.training_effect) dynItems.push(metric(act.training_effect.toFixed(1), '训练效果', 'spark'));
        if (act.vo2max) dynItems.push(metric(Math.round(act.vo2max), 'VO2max', 'lungs'));
        if (act.lactate_threshold) dynItems.push(metric(`${Math.round(act.lactate_threshold)} ${u('bpm')}`, '乳酸阈值', 'target'));

        const splitSummary = buildSplitSummary(splits);
        detail.innerHTML = `
            <div class="card activity-detail-card">
                <div class="activity-detail-head">
                    <div class="activity-logo" data-icon="runner">${iconSvg('runner')}</div>
                    <div class="activity-title-block">
                        <div class="page-kicker">${typeLabel(act.type)} · ${formatDateTime(act.start_time, true)}</div>
                        <h2>${escapeHtml(act.name)}</h2>
                        <div class="activity-subline">
                            <span>${iconSvg('route')}${safeKm(act.distance)} km</span>
                            <span>${iconSvg('clock')}${formatDuration(act.duration)}</span>
                            <span>${iconSvg('timer')}${formatPace(act.avg_pace)} /km</span>
                            <span>${iconSvg('heart')}${roundOrDash(act.avg_heart_rate)} bpm</span>
                        </div>
                        ${renderWeatherLine(act)}
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="document.getElementById('act-detail').style.display='none'">关闭</button>
                </div>

                <div class="detail-grid">
                    <div>
                        <h3>基础指标</h3>
                        <div class="metric-grid">${basicItems.join('')}</div>
                    </div>
                    <div>
                        <h3>跑步动态</h3>
                        <div class="metric-grid">${dynItems.join('') || '<div class="empty-state">暂无跑步动态</div>'}</div>
                    </div>
                </div>

                <div class="split-section">
                    <div class="section-title">
                        <h2>分段数据</h2>
                        <span class="muted small">${splits.length ? `${splits.length} 段` : '暂无数据'}</span>
                    </div>
                    ${renderSplitSummary(splitSummary)}
                    ${renderSplitTable(splitSummary)}
                </div>
            </div>
        `;
        window.scrollTo({ top: detail.offsetTop - 76, behavior: 'smooth' });
    } catch (err) {
        showToast('加载详情失败：' + err.message, 'error');
        detail.style.display = 'none';
    }
}

function buildSplitSummary(splits) {
    const rows = splits.filter(s => Number(s.distance) > 0 && Number(s.duration) > 0);
    if (!rows.length) return null;
    const fastest = rows.reduce((best, s) => splitPace(s) < splitPace(best) ? s : best, rows[0]);
    const slowest = rows.reduce((worst, s) => splitPace(s) > splitPace(worst) ? s : worst, rows[0]);
    const half = Math.max(1, Math.floor(rows.length / 2));
    const first = rows.slice(0, half);
    const second = rows.slice(half);
    const firstPace = groupPace(first);
    const secondPace = second.length ? groupPace(second) : firstPace;
    const firstHr = avg(first.map(s => s.avg_heart_rate));
    const secondHr = second.length ? avg(second.map(s => s.avg_heart_rate)) : firstHr;
    const interval = detectInterval(rows);
    return {
        rows,
        fastest,
        slowest,
        firstPace,
        secondPace,
        hrDrift: firstHr && secondHr ? secondHr - firstHr : null,
        interval,
        stable: firstPace && secondPace ? Math.abs(secondPace - firstPace) <= 8 : false
    };
}

function renderSplitSummary(summary) {
    if (!summary) return '<div class="empty-state">暂无分段数据</div>';
    const paceDiff = summary.firstPace && summary.secondPace ? summary.secondPace - summary.firstPace : null;
    const driftText = summary.hrDrift == null ? '-' : `${summary.hrDrift >= 0 ? '+' : ''}${Math.round(summary.hrDrift)} bpm`;
    const badgeText = summary.interval ? '疑似间歇' : (summary.stable ? '配速稳定' : '配速波动');
    const badgeClass = summary.interval ? 'warning' : (summary.stable ? 'good' : 'neutral');
    return `
        <div class="split-summary-grid">
            ${splitSummaryItem(summary.rows.length, '总分段', 'layers')}
            ${splitSummaryItem(`第${summary.fastest.split_index}段 ${formatPace(splitPace(summary.fastest))}`, '最快分段', 'fast')}
            ${splitSummaryItem(`第${summary.slowest.split_index}段 ${formatPace(splitPace(summary.slowest))}`, '最慢分段', 'slow')}
            ${splitSummaryItem(paceDiff == null ? '-' : `${paceDiff >= 0 ? '+' : ''}${Math.round(paceDiff)} s/km`, '前后半程', 'compare')}
            ${splitSummaryItem(driftText, '心率漂移', 'pulse')}
            <div class="split-summary-item">
                <span class="split-status ${badgeClass}">${iconSvg(summary.interval ? 'repeat' : 'check')}${badgeText}</span>
                <small>${summary.interval || '基于分段配速与心率变化'}</small>
            </div>
        </div>
    `;
}

function splitSummaryItem(value, label, icon) {
    return `
        <div class="split-summary-item">
            <div class="split-summary-icon" data-icon="${icon}">${iconSvg(icon)}</div>
            <strong>${value}</strong>
            <small>${label}</small>
        </div>
    `;
}

function renderSplitTable(summary) {
    if (!summary) return '';
    const fastestId = summary.fastest?.id;
    const slowestId = summary.slowest?.id;
    return `
        <div class="table-wrap split-table-wrap">
            <table class="split-table">
                <thead>
                    <tr>
                        <th>段</th><th>类型</th><th>距离</th><th>用时</th><th>配速</th>
                        <th>平均心率</th><th>最高心率</th><th>步频</th><th>功率</th><th>爬升</th>
                    </tr>
                </thead>
                <tbody>
                    ${summary.rows.map(s => {
                        const rowClass = [
                            s.id === fastestId ? 'split-fastest' : '',
                            s.id === slowestId ? 'split-slowest' : '',
                            isRestSplit(s) ? 'split-rest' : ''
                        ].filter(Boolean).join(' ');
                        return `
                            <tr class="${rowClass}">
                                <td><span class="split-index">${s.split_index}</span></td>
                                <td>${splitTypeLabel(s.split_type)}</td>
                                <td>${safeKm(s.distance)} km</td>
                                <td>${formatDuration(s.duration)}</td>
                                <td><strong>${formatPace(splitPace(s))}</strong></td>
                                <td>${roundOrDash(s.avg_heart_rate)}</td>
                                <td>${roundOrDash(s.max_heart_rate)}</td>
                                <td>${roundOrDash(s.avg_cadence)}</td>
                                <td>${roundOrDash(s.avg_power)}</td>
                                <td>${roundOrDash(s.elevation_gain)} m</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function iconSvg(name) {
    const paths = {
        runner: '<path d="M13 4.5a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z"/><path d="m11 7-2.5 3 2.4 2.2-1.4 5.3"/><path d="m8.5 10-3 .8"/><path d="m10.9 12.2 2.6 1.4 2.2 3.4"/><path d="m9.5 17.5-3 2.5"/>',
        route: '<path d="M4 18c4 0 3-12 7-12h1"/><path d="M13 6h7"/><path d="M17 3l3 3-3 3"/><circle cx="4" cy="18" r="2"/>',
        clock: '<circle cx="12" cy="12" r="8"/><path d="M12 8v5l3 2"/>',
        timer: '<path d="M10 2h4"/><path d="M12 14l3-3"/><circle cx="12" cy="13" r="8"/>',
        heart: '<path d="M20.5 8.5c0 5-8.5 10-8.5 10s-8.5-5-8.5-10a4.7 4.7 0 0 1 8.5-2.7 4.7 4.7 0 0 1 8.5 2.7Z"/>',
        pulse: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
        mountain: '<path d="m3 19 7-12 4 7 2-3 5 8Z"/>',
        steps: '<path d="M8 20c2 0 3-1.2 3-3 0-2-1.3-3-3-3s-3 1-3 3 1 3 3 3Z"/><path d="M16 10c2 0 3-1.2 3-3 0-2-1.3-3-3-3s-3 1-3 3 1 3 3 3Z"/>',
        speed: '<path d="M4 14a8 8 0 1 1 16 0"/><path d="m12 14 4-4"/><path d="M12 14h.01"/>',
        foot: '<path d="M7 20c3-1 4-3 4-6 0-3-1-6-3-8C6 4 4 5 4 8c0 5 1 9 3 12Z"/><path d="M14 20c3-1 5-3 5-6 0-2-1-4-3-4s-3 2-3 4c0 2 .3 4 1 6Z"/>',
        wave: '<path d="M3 12c2-4 4-4 6 0s4 4 6 0 4-4 6 0"/>',
        stride: '<path d="M4 17h16"/><path d="M6 14l3-6 4 4 5-7"/><path d="M16 5h2v2"/>',
        spark: '<path d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6Z"/>',
        lungs: '<path d="M12 12V4"/><path d="M12 12c-2-4-6-5-7-1-.7 3 .2 7 3 8 2 .7 4-1 4-4"/><path d="M12 12c2-4 6-5 7-1 .7 3-.2 7-3 8-2 .7-4-1-4-4"/>',
        target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
        layers: '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
        fast: '<path d="M4 13h8"/><path d="M4 7h12"/><path d="m14 17 5-5-5-5"/>',
        slow: '<circle cx="12" cy="12" r="8"/><path d="M12 8v5h4"/>',
        compare: '<path d="M7 7h12l-3-3"/><path d="M17 17H5l3 3"/>',
        repeat: '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>',
        check: '<path d="m5 12 4 4L19 6"/>'
    };
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.spark}</svg>`;
}

function detectInterval(rows) {
    const restCount = rows.filter(isRestSplit).length;
    if (restCount) return `包含 ${restCount} 个恢复/休息段`;
    if (rows.length < 4) return '';
    const paces = rows.map(splitPace).filter(Boolean).sort((a, b) => a - b);
    const mid = Math.floor(paces.length / 2);
    const median = paces.length % 2 ? paces[mid] : (paces[mid - 1] + paces[mid]) / 2;
    const fast = rows.filter(s => splitPace(s) <= median * 0.9).length;
    const slow = rows.filter(s => splitPace(s) >= median * 1.15).length;
    return fast >= 2 && slow >= 2 ? `快慢段交替，快段 ${fast} 个、慢段 ${slow} 个` : '';
}

function groupPace(rows) {
    const distance = rows.reduce((sum, s) => sum + Number(s.distance || 0), 0);
    const duration = rows.reduce((sum, s) => sum + Number(s.duration || 0), 0);
    return distance > 0 ? duration / (distance / 1000) : null;
}

function splitPace(split) {
    return Number(split.avg_pace || (split.distance ? split.duration / (split.distance / 1000) : 0));
}

function avg(values) {
    const nums = values.map(Number).filter(Number.isFinite).filter(v => v > 0);
    return nums.length ? nums.reduce((sum, v) => sum + v, 0) / nums.length : null;
}

function isRestSplit(split) {
    const type = String(split.split_type || '').toUpperCase();
    return Number(split.distance || 0) < 200 || type.includes('REST') || type.includes('RECOVERY');
}

function splitTypeLabel(type) {
    const raw = String(type || '1km');
    if (raw.toUpperCase().includes('REST')) return '休息';
    if (raw.toUpperCase().includes('RECOVERY')) return '恢复';
    if (raw === '1km') return '1 km';
    return escapeHtml(raw.replaceAll('_', ' '));
}

function renderWeatherLine(act) {
    const weatherParts = [];
    if (act.temperature != null) weatherParts.push(`${act.temperature.toFixed(1)}°C`);
    if (act.humidity != null) weatherParts.push(`湿度 ${Math.round(act.humidity)}%`);
    if (act.wind_speed != null) weatherParts.push(`风速 ${act.wind_speed.toFixed(1)} km/h`);
    if (act.weather_condition) weatherParts.push(act.weather_condition);
    return weatherParts.length ? `<div class="weather-line">天气：${weatherParts.join(' / ')}</div>` : '';
}

function safeKm(value) {
    return Number(value || 0) ? (Number(value) / 1000).toFixed(2) : '-';
}

function roundOrDash(value) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? Math.round(n) : '-';
}

function formatDateTime(value, withTime = true) {
    if (!value) return '-';
    return withTime ? value.slice(0, 16) : value.slice(0, 10);
}

function typeLabel(type) {
    const map = {
        running: '跑步',
        track_running: '田径场跑',
        treadmill_running: '跑步机',
        indoor_running: '室内跑',
        strength_training: '力量训练',
        cycling: '骑行',
        swimming: '游泳',
        lap_swimming: '游泳'
    };
    return map[type] || type || '其他';
}

function formatDuration(seconds) {
    if (!seconds) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
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
