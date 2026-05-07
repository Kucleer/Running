registerPage('#dashboard', async (container) => {
    const today = new Date().toISOString().split('T')[0];

    container.innerHTML = `
        <h1>训练仪表盘</h1>

        <div class="card">
            <div class="quick-filters">
                <span class="pill active" data-range="all">所有</span>
                <span class="pill" data-range="year">近一年</span>
                <span class="pill" data-range="6m">近半年</span>
                <span class="pill" data-range="3m">近三月</span>
                <span class="pill" data-range="month">近一月</span>
                <span class="pill" data-range="week">近一周</span>
            </div>
            <div class="filter-bar">
                <div><label>开始日期</label><input id="dash-date-from" type="date"></div>
                <div><label>结束日期</label><input id="dash-date-to" type="date" value="${today}"></div>
                <button class="btn" id="dash-filter-btn" style="height:40px">自定义筛选</button>
            </div>
        </div>

        <div id="summary-line" class="summary-line"></div>
        <div id="stats-cards" class="stats-grid"></div>

        <div class="card" id="vdot-card" style="margin-top:16px">
            <div class="flex-between">
                <h2>跑力 (VDOT)</h2>
                <button class="collapse-toggle" id="vdot-toggle" onclick="toggleVDOT()">
                    <span class="arrow" id="vdot-arrow">&#9654;</span> 展开详情
                </button>
            </div>
            <div id="vdot-summary" class="stats-grid"></div>
            <div id="vdot-detail" style="display:none;margin-top:14px"></div>
        </div>

        <div class="card" style="margin-top:16px">
            <h2>健康数据</h2>
            <div id="health-cards" class="stats-grid"></div>
            <div class="chart-wrap" style="height:200px;margin-top:12px"><canvas id="healthChart"></canvas></div>
        </div>

        <div class="card" style="margin-top:16px">
            <div class="charts-row">
                <div class="chart-col">
                    <h3>月度跑量趋势</h3>
                    <div class="chart-wrap"><canvas id="monthlyChart"></canvas></div>
                </div>
                <div class="chart-col">
                    <h3>配速分布</h3>
                    <div class="chart-wrap"><canvas id="paceChart"></canvas></div>
                </div>
            </div>
        </div>
    `;

    let vdotData = null;

    function setDateRange(range) {
        const to = today;
        let from = '1970-01-01';
        const d = new Date();
        switch (range) {
            case 'week': d.setDate(d.getDate() - 7); break;
            case 'month': d.setMonth(d.getMonth() - 1); break;
            case '3m': d.setMonth(d.getMonth() - 3); break;
            case '6m': d.setMonth(d.getMonth() - 6); break;
            case 'year': d.setFullYear(d.getFullYear() - 1); break;
            default: from = '1970-01-01'; break;
        }
        if (range !== 'all') from = d.toISOString().split('T')[0];
        document.getElementById('dash-date-from').value = from;
        document.getElementById('dash-date-to').value = to;
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        const target = document.querySelector(`.pill[data-range="${range}"]`);
        if (target) target.classList.add('active');
        loadStats();
    }

    document.querySelectorAll('.pill').forEach(pill => {
        pill.onclick = () => setDateRange(pill.dataset.range);
    });

    async function loadStats() {
        const from = document.getElementById('dash-date-from').value;
        const to = document.getElementById('dash-date-to').value;

        try {
            const data = await API.stats('monthly', from, to + ' 23:59:59');
            const totalKm = ((data.overview.total_distance || 0) / 1000);
            const totalRuns = data.overview.total_runs || 0;
            document.getElementById('summary-line').innerHTML =
                `统计区间内 <strong>${totalRuns}</strong> 次跑步 · 总跑量 <strong>${totalKm.toFixed(1)} km</strong>`;
            renderStatsCards(data.overview);
            renderMonthlyChart(data.monthly);
            renderPaceChart(data.pace_distribution);
        } catch (err) {
            document.getElementById('stats-cards').innerHTML = `<p style="color:red">加载失败: ${err.message}</p>`;
        }
    }

    async function loadVDOT() {
        try {
            vdotData = await API.vdot();
            renderVDOTSummary(vdotData);
            if (vdotData.vdot) renderVDOTDetail(vdotData);
        } catch (err) {
            document.getElementById('vdot-card').innerHTML = '<h2>跑力 (VDOT)</h2><p style="color:var(--text-muted)">加载失败</p>';
        }
    }

    document.getElementById('dash-filter-btn').onclick = loadStats;

    setDateRange('all');
    loadVDOT();
    loadHealth();
});

window.toggleVDOT = function() {
    const detail = document.getElementById('vdot-detail');
    const arrow = document.getElementById('vdot-arrow');
    const toggle = document.getElementById('vdot-toggle');
    if (!detail || !arrow || !toggle) return;
    const isOpen = detail.style.display !== 'none';
    if (isOpen) {
        detail.style.display = 'none';
        arrow.classList.remove('open');
        toggle.innerHTML = '<span class="arrow" id="vdot-arrow">&#9654;</span> 展开详情';
    } else {
        detail.style.display = 'block';
        document.getElementById('vdot-arrow').classList.add('open');
        document.getElementById('vdot-toggle').innerHTML = '<span class="arrow open" id="vdot-arrow">&#9654;</span> 收起详情';
    }
};

function renderStatsCards(overview) {
    const totalKm = ((overview.total_distance || 0) / 1000).toFixed(1);
    const totalHr = overview.total_duration ? (overview.total_duration / 3600).toFixed(1) : '-';
    const avgPace = formatPace(overview.avg_pace);

    document.getElementById('stats-cards').innerHTML = `
        <div class="stat-card"><div class="value">${overview.total_runs || 0}</div><div class="label">跑步次数</div></div>
        <div class="stat-card"><div class="value">${totalKm}</div><div class="label">总跑量 (km)</div></div>
        <div class="stat-card"><div class="value">${totalHr}</div><div class="label">总时长 (h)</div></div>
        <div class="stat-card"><div class="value">${avgPace}</div><div class="label">平均配速 /km</div></div>
        <div class="stat-card"><div class="value">${Math.round(overview.avg_hr) || '-'}</div><div class="label">平均心率 (bpm)</div></div>
    `;
}

function renderVDOTSummary(vd) {
    const el = document.getElementById('vdot-summary');
    if (!el) return;
    if (!vd.vdot) {
        el.innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1">暂无足够数据（需要 3km 以上的跑步记录）</p>';
        document.getElementById('vdot-toggle').style.display = 'none';
        return;
    }
    el.innerHTML = `
        <div class="stat-card"><div class="value">${vd.vdot}</div><div class="label">VDOT</div></div>
        <div class="stat-card"><div class="value small">${vd.source||'-'}</div><div class="label">最佳来源</div></div>
        ${vd.best_5k ? `<div class="stat-card"><div class="value small">${vd.best_5k}</div><div class="label">最佳 5K</div></div>` : ''}
    `;
}

function renderVDOTDetail(vd) {
    const el = document.getElementById('vdot-detail');
    if (!el) return;

    const paceRows = Object.entries(vd.pace_zones).map(([name, z]) =>
        `<tr><td>${name}</td><td>${z.fast} ~ ${z.slow} /km</td></tr>`
    ).join('');

    const predRows = Object.entries(vd.predictions).map(([name, time]) =>
        `<tr><td>${name}</td><td>${time}</td></tr>`
    ).join('');

    let hrHtml = '';
    if (Object.keys(vd.hr_zones).length > 0) {
        hrHtml = `<h3 style="margin-top:18px">心率区间 (储备心率法)</h3>
            <table style="margin-top:6px"><thead><tr><th>区间</th><th>心率 (bpm)</th></tr></thead><tbody>` +
            Object.entries(vd.hr_zones).map(([name, rng]) => `<tr><td>${name}</td><td>${rng}</td></tr>`).join('') +
            '</tbody></table>';
    }

    el.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
            <div>
                <h3>成绩预测</h3>
                <table style="margin-top:6px"><thead><tr><th>距离</th><th>预测成绩</th></tr></thead><tbody>${predRows}</tbody></table>
            </div>
            <div>
                <h3>训练配速区间</h3>
                <table style="margin-top:6px"><thead><tr><th>类型</th><th>配速</th></tr></thead><tbody>${paceRows}</tbody></table>
            </div>
        </div>
        ${hrHtml}
    `;
}

let _charts = {};

function renderMonthlyChart(monthly) {
    const canvas = document.getElementById('monthlyChart');
    if (!canvas) return;
    if (_charts.monthly) _charts.monthly.destroy();
    _charts.monthly = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: monthly.map(m => m.month),
            datasets: [{
                label: '跑量 (km)',
                data: monthly.map(m => (m.distance / 1000).toFixed(1)),
                backgroundColor: '#e94560',
                borderRadius: 4,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, grid: { color: '#f0f0f0' } }, x: { grid: { display: false } } }
        }
    });
}

function renderPaceChart(paceDist) {
    const canvas = document.getElementById('paceChart');
    if (!canvas) return;
    if (_charts.pace) _charts.pace.destroy();
    _charts.pace = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: paceDist.map(p => p.pace_range),
            datasets: [{
                data: paceDist.map(p => p.count),
                backgroundColor: ['#e94560','#f77f6e','#f9a87a','#facf8a','#e0e0e0','#c0c0c0','#999'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right', labels: { padding: 12, usePointStyle: true } } }
        }
    });
}

function formatPace(seconds) {
    if (!seconds || seconds === 0) return '-';
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${String(sec).padStart(2, '0')}`;
}

async function loadHealth() {
    try {
        const data = await API.healthData(14);
        renderHealthCards(data);
        renderHealthChart(data);
    } catch (err) {
        document.getElementById('health-cards').innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1">暂无健康数据，请在设置页同步</p>';
    }
}

function renderHealthCards(data) {
    const el = document.getElementById('health-cards');
    if (!el) return;
    if (!data.length) {
        el.innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1">暂无健康数据，请在设置页执行「同步健康数据」</p>';
        return;
    }
    const latest = data[data.length - 1];
    const prev = data.length > 1 ? data[data.length - 2] : null;

    function trend(curr, prev_val, unit) {
        if (!prev_val || !curr) return '';
        const diff = curr - prev_val;
        if (Math.abs(diff) < 0.5) return '';
        return `<span style="font-size:11px;color:${diff>0?'#2ecc71':'#e74c3c'}"> ${diff>0?'+':''}${Math.round(diff*10)/10}${unit}</span>`;
    }

    const cards = [];
    if (latest.sleep_score) {
        cards.push(`<div class="stat-card"><div class="value">${latest.sleep_score}</div><div class="label">睡眠分数${trend(latest.sleep_score, prev?.sleep_score, '')}</div></div>`);
    }
    if (latest.sleep_duration) {
        cards.push(`<div class="stat-card"><div class="value">${latest.sleep_duration}h</div><div class="label">睡眠时长${trend(latest.sleep_duration, prev?.sleep_duration, 'h')}</div></div>`);
    }
    if (latest.hrv_avg) {
        cards.push(`<div class="stat-card"><div class="value">${Math.round(latest.hrv_avg)}</div><div class="label">HRV (ms)${trend(latest.hrv_avg, prev?.hrv_avg, '')}</div></div>`);
    }
    if (latest.resting_hr) {
        cards.push(`<div class="stat-card"><div class="value">${Math.round(latest.resting_hr)}</div><div class="label">静息心率${trend(latest.resting_hr, prev?.resting_hr, 'bpm')}</div></div>`);
    }
    if (latest.avg_stress) {
        cards.push(`<div class="stat-card"><div class="value">${Math.round(latest.avg_stress)}</div><div class="label">平均压力</div></div>`);
    }
    if (latest.body_battery_max) {
        cards.push(`<div class="stat-card"><div class="value">${latest.body_battery_max}/${latest.body_battery_min||'-'}</div><div class="label">身体电量 (高/低)</div></div>`);
    }
    if (latest.vo2max) {
        cards.push(`<div class="stat-card"><div class="value">${Math.round(latest.vo2max)}</div><div class="label">VO2max</div></div>`);
    }
    if (latest.hrv_status) {
        cards.push(`<div class="stat-card"><div class="value" style="font-size:16px">${latest.hrv_status}</div><div class="label">HRV 状态</div></div>`);
    }
    el.innerHTML = cards.join('') || '<p style="color:var(--text-muted);grid-column:1/-1">暂无数据</p>';
}

function renderHealthChart(data) {
    const canvas = document.getElementById('healthChart');
    if (!canvas || !data.length) return;
    if (_charts.health) _charts.health.destroy();

    const labels = data.map(d => (d.date||'').slice(5));
    const hrvs = data.map(d => d.hrv_avg || null);
    const sleeps = data.map(d => d.sleep_score || null);

    _charts.health = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'HRV (ms)',
                    data: hrvs,
                    borderColor: '#e94560',
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    pointRadius: 3,
                    yAxisID: 'y',
                },
                {
                    label: '睡眠分数',
                    data: sleeps,
                    borderColor: '#4a90d9',
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    pointRadius: 3,
                    yAxisID: 'y1',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 20 } } },
            scales: {
                y: { type: 'linear', position: 'left', grid: { color: '#f0f0f0' } },
                y1: { type: 'linear', position: 'right', min: 0, max: 100, grid: { display: false } }
            }
        }
    });
}
