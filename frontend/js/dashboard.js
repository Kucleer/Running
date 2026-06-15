registerPage('#dashboard', async (container) => {
    const today = new Date().toISOString().split('T')[0];

    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">Dashboard</div>
                <h1>训练仪表盘</h1>
            </div>
            <div class="dashboard-filter">
                <div class="quick-filters">
                    <span class="pill active" data-range="all">全部</span>
                    <span class="pill" data-range="year">近一年</span>
                    <span class="pill" data-range="6m">近半年</span>
                    <span class="pill" data-range="3m">近三个月</span>
                    <span class="pill" data-range="month">近一个月</span>
                    <span class="pill" data-range="week">近一周</span>
                </div>
                <input id="dash-date-from" type="date">
                <input id="dash-date-to" type="date" value="${today}">
                <button class="btn" id="dash-filter-btn">应用筛选</button>
                <button class="btn btn-secondary" id="dash-range-month">本月</button>
                <button class="btn btn-secondary" id="dash-range-year">本年</button>
            </div>
        </div>

        <div id="summary-line" class="summary-line"></div>
        <div id="stats-cards" class="dashboard-kpi-grid"></div>

        <div class="dashboard-main-grid">
            <div class="card dashboard-card-tall" id="vdot-card">
                <div class="section-title">
                    <h2>VDOT</h2>
                    <button class="collapse-toggle" id="vdot-toggle" onclick="toggleVDOT()">
                        <span class="arrow" id="vdot-arrow">&#9654;</span> 展开详情
                    </button>
                </div>
                <div id="vdot-summary"></div>
                <div id="vdot-detail" style="display:none;margin-top:10px"></div>
            </div>
            <div class="card dashboard-card-tall">
                <div class="section-title"><h2>月度跑量趋势</h2></div>
                <div class="chart-wrap"><canvas id="monthlyChart"></canvas></div>
            </div>
            <div class="card dashboard-card-tall">
                <div class="section-title"><h2>配速分布</h2></div>
                <div class="pace-chart-container">
                    <div class="chart-wrap donut"><canvas id="paceChart"></canvas></div>
                    <div class="pace-legend"></div>
                </div>
            </div>
        </div>

        <div class="dashboard-lower-grid">
            <div class="card dashboard-card-mid health-card">
                <div class="section-title"><h2>健康恢复</h2></div>
                <div id="health-cards" class="stats-grid"></div>
                <div class="chart-wrap compact"><canvas id="healthChart"></canvas></div>
            </div>
            <div class="card dashboard-card-mid">
                <div class="section-title"><h2>最近训练</h2></div>
                <div id="recent-training" class="table-wrap"></div>
            </div>
        </div>
    `;

    document.querySelectorAll('.pill').forEach(pill => {
        pill.onclick = () => setDateRange(pill.dataset.range);
    });
    document.getElementById('dash-filter-btn').onclick = loadDashboard;
    document.getElementById('dash-range-month').onclick = () => setDateRange('thisMonth');
    document.getElementById('dash-range-year').onclick = () => setDateRange('thisYear');

    setDateRange('all');

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
            case 'thisMonth':
                from = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
                break;
            case 'thisYear':
                from = `${d.getFullYear()}-01-01`;
                break;
            default: from = '1970-01-01'; break;
        }
        if (!['all', 'thisMonth', 'thisYear'].includes(range)) from = d.toISOString().split('T')[0];
        document.getElementById('dash-date-from').value = from;
        document.getElementById('dash-date-to').value = to;
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        const target = document.querySelector(`.pill[data-range="${range}"]`);
        if (target) target.classList.add('active');
        loadDashboard();
    }

    async function loadDashboard() {
        const from = document.getElementById('dash-date-from').value;
        const to = document.getElementById('dash-date-to').value;

        try {
            const [stats, vdot, health] = await Promise.all([
                API.stats('monthly', from, to + ' 23:59:59'),
                API.vdot(),
                API.healthData(14, from, to)
            ]);
            const recentActivities = await API.activities({ type: 'running', from, to: to + ' 23:59:59' });

            const totalKm = ((stats.overview.total_distance || 0) / 1000);
            const totalRuns = stats.overview.total_runs || 0;
            document.getElementById('summary-line').innerHTML =
                `当前区间 <strong>${totalRuns}</strong> 次跑步 / 总跑量 <strong>${totalKm.toFixed(1)} km</strong>`;

            renderStatsCards(stats.overview, stats.monthly, vdot, health);
            renderMonthlyChart(stats.monthly);
            renderPaceChart(stats.pace_distribution);
            renderVDOTSummary(vdot);
            renderVDOTDetail(vdot);
            renderHealthCards(health);
            renderHealthChart(health);
            renderRecentTraining(recentActivities.slice(0, 5));
        } catch (err) {
            document.getElementById('stats-cards').innerHTML = `<div class="empty-state error-text">加载失败：${err.message}</div>`;
        }
    }
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
        arrow.classList.add('open');
        toggle.innerHTML = '<span class="arrow open" id="vdot-arrow">&#9654;</span> 收起详情';
    }
};

function renderStatsCards(overview, monthly = [], vd = {}, health = []) {
    const totalKm = ((overview.total_distance || 0) / 1000).toFixed(1);
    const avgPace = formatPace(overview.avg_pace);
    const vdotValue = vd.vdot ? Number(vd.vdot).toFixed(1) : '-';
    const recovery = recoveryScore(health);
    const distanceSeries = monthly.map(m => Number((m.distance / 1000).toFixed(1)));
    const paceSeries = monthly.map(m => m.avg_pace || 0).filter(Boolean).map(v => Math.max(0, 720 - v));
    const healthSeries = health.map(d => d.sleep_score || d.body_battery_max || d.hrv_avg || 0).filter(Boolean);
    const fallback = [2, 5, 4, 7, 5, 9, 8, 10];

    document.getElementById('stats-cards').innerHTML = `
        ${kpiCard('⌁', totalKm, '总跑量', 'km', '较上月 <strong>--</strong>', sparkline(distanceSeries.length ? distanceSeries : fallback, ''))}
        ${kpiCard('◷', avgPace, '平均配速', '/km', '当前区间', sparkline(paceSeries.length ? paceSeries : fallback, 'blue'))}
        ${kpiCard('V', vdotValue, 'VDOT', '', vdotLabel(vd.vdot || 0), sparkline(paceSeries.length ? paceSeries : fallback, 'green'))}
        ${kpiCard('♡', recovery.value, '健康恢复', recovery.unit, recovery.label, sparkline(healthSeries.length ? healthSeries : fallback, 'accent'))}
    `;
}

function kpiCard(icon, value, label, unit, sub, graph) {
    return `
        <div class="stat-card kpi-card">
            <div class="kpi-icon">${icon}</div>
            <div>
                <div class="label">${label}</div>
                <div class="value">${value}<span class="metric-unit">${unit ? ' ' + unit : ''}</span></div>
                <div class="kpi-sub">${sub}</div>
            </div>
            ${graph}
        </div>
    `;
}

function recoveryScore(health) {
    const latest = [...health].reverse().find(d => d.sleep_score || d.body_battery_max || d.hrv_avg);
    if (!latest) return { value: '-', unit: '', label: '暂无健康数据' };
    if (latest.sleep_score) return { value: latest.sleep_score, unit: '%', label: '睡眠恢复' };
    if (latest.body_battery_max) return { value: latest.body_battery_max, unit: '%', label: '身体电量' };
    return { value: Math.round(latest.hrv_avg), unit: 'ms', label: 'HRV' };
}

function sparkline(values, tone = '') {
    const clean = values.map(v => Number(v) || 0);
    const min = Math.min(...clean);
    const max = Math.max(...clean);
    const span = max - min || 1;
    const points = clean.map((v, i) => {
        const x = clean.length === 1 ? 43 : (i / (clean.length - 1)) * 82 + 2;
        const y = 34 - ((v - min) / span) * 28;
        return [x, y];
    });
    const line = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
    const area = `${line} L84 38 L2 38 Z`;
    return `<svg class="sparkline ${tone}" viewBox="0 0 86 40" aria-hidden="true">
        <path class="area" d="${area}"></path>
        <path d="${line}"></path>
    </svg>`;
}

function renderVDOTSummary(vd) {
    const el = document.getElementById('vdot-summary');
    if (!el) return;
    if (!vd.vdot) {
        el.innerHTML = '<div class="empty-state">暂无足够数据，需要 5km 以上的跑步记录。</div>';
        document.getElementById('vdot-toggle').style.display = 'none';
        return;
    }

    const vdotValue = Number(vd.vdot).toFixed(1);
    const vdotProgress = `${Math.max(8, Math.min(92, (Number(vd.vdot) / 70) * 100)).toFixed(1)}%`;
    el.innerHTML = `
        <div class="vdot-panel">
            <div class="vdot-gauge" style="--vdot-progress:${vdotProgress}">
                <div class="vdot-score">
                    <strong>${vdotValue}</strong>
                    <span>${vdotLabel(vd.vdot)}</span>
                </div>
            </div>
            <div class="vdot-list">
                <div class="vdot-list-row"><span>最佳来源</span><strong>${vd.source || '-'}</strong></div>
                ${vd.best_5k ? `<div class="vdot-list-row"><span>最佳 5K</span><strong>${vd.best_5k}</strong></div>` : ''}
                ${predictionRow(vd.predictions, '10K')}
                ${predictionRow(vd.predictions, '半马')}
                ${predictionRow(vd.predictions, '全马')}
            </div>
        </div>
    `;
}

function predictionRow(predictions = {}, key) {
    const value = predictions[key] || predictions[legacyRaceKey(key)];
    return value ? `<div class="vdot-list-row"><span>预测 ${key}</span><strong>${value}</strong></div>` : '';
}

function legacyRaceKey(key) {
    return ({ '半马': '鍗婇┈', '全马': '鍏ㄩ┈' })[key] || key;
}

function vdotLabel(vdot) {
    if (vdot >= 55) return '优秀';
    if (vdot >= 45) return '良好';
    if (vdot >= 35) return '稳定';
    return '基础';
}

function renderVDOTDetail(vd) {
    const el = document.getElementById('vdot-detail');
    if (!el || !vd.vdot) return;
    const predRows = Object.entries(normalizePredictions(vd.predictions)).map(([name, time]) =>
        `<tr><td>${name}</td><td>${time}</td></tr>`
    ).join('');
    el.innerHTML = `<div class="table-wrap"><table><thead><tr><th>距离</th><th>预测成绩</th></tr></thead><tbody>${predRows}</tbody></table></div>`;
}

function normalizePredictions(predictions = {}) {
    return {
        '5K': predictions['5K'],
        '10K': predictions['10K'],
        '半马': predictions['半马'] || predictions['鍗婇┈'],
        '全马': predictions['全马'] || predictions['鍏ㄩ┈']
    };
}

function zoneName(name) {
    const map = {
        '杞绘澗璺?(E)': '轻松跑 E',
        '椹媺鏉鹃厤閫?(M)': '马拉松配速 M',
        '涔抽吀闃堝€?(T)': '乳酸阈值 T',
        '闂存瓏璺?(I)': '间歇跑 I',
        '閲嶅璺?(R)': '重复跑 R'
    };
    return map[name] || name;
}

function buildVDOTPaceDistribution(activities, vd, fallback = []) {
    if (!vd?.pace_zones || !Object.keys(vd.pace_zones).length) return fallback;

    const preferred = ['轻松跑 E', '马拉松配速 M', '乳酸阈值 T', '间歇跑 I', '重复跑 R'];
    const entries = Object.entries(vd.pace_zones)
        .map(([name, zone]) => ({
            name: zoneName(name),
            fast: paceToSeconds(zone.fast),
            slow: paceToSeconds(zone.slow),
            count: 0
        }))
        .filter(z => z.fast && z.slow)
        .sort((a, b) => {
            const ai = preferred.indexOf(a.name);
            const bi = preferred.indexOf(b.name);
            if (ai !== -1 || bi !== -1) return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
            return a.fast - b.fast;
        });

    if (!entries.length) return fallback;

    for (const activity of activities) {
        const pace = Number(activity.avg_pace || 0);
        const distanceKm = Number(activity.distance || 0) / 1000;
        if (!pace) continue;
        if (!distanceKm) continue;
        let target = entries.find(z => pace >= z.fast && pace <= z.slow);
        if (!target) {
            const fastest = entries.reduce((best, z) => z.fast < best.fast ? z : best, entries[0]);
            const slowest = entries.reduce((best, z) => z.slow > best.slow ? z : best, entries[0]);
            if (pace < fastest.fast) target = fastest;
            else if (pace > slowest.slow) target = slowest;
            else target = entries.reduce((best, z) => {
                const gap = Math.min(Math.abs(pace - z.fast), Math.abs(pace - z.slow));
                const bestGap = Math.min(Math.abs(pace - best.fast), Math.abs(pace - best.slow));
                return gap < bestGap ? z : best;
            }, entries[0]);
        }
        if (target) target.count += distanceKm;
    }

    return entries.map(z => ({
        pace_range: `${z.name} ${formatPace(z.fast)}-${formatPace(z.slow)}`,
        count: Number(z.count.toFixed(2))
    }));
}

function paceToSeconds(value) {
    if (!value || typeof value !== 'string') return 0;
    const [min, sec] = value.split(':').map(Number);
    if (!Number.isFinite(min) || !Number.isFinite(sec)) return 0;
    return min * 60 + sec;
}

function renderRecentTraining(activities) {
    const el = document.getElementById('recent-training');
    if (!el) return;
    if (!activities.length) {
        el.innerHTML = '<div class="empty-state">暂无最近训练</div>';
        return;
    }

    const rows = activities.map(a => `
        <tr>
            <td>${activityIcon(a.type)} ${escapeHtml(a.name || '跑步')}</td>
            <td>${(a.start_time || '').slice(0, 10)}</td>
            <td>${a.distance ? (a.distance / 1000).toFixed(1) + ' km' : '-'}</td>
            <td>${formatPace(a.avg_pace)} /km</td>
            <td>${Math.round(a.avg_heart_rate) || '-'}</td>
        </tr>
    `).join('');

    el.innerHTML = `
        <table class="recent-training-table">
            <thead><tr><th>活动</th><th>日期</th><th>距离</th><th>配速</th><th>心率</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

function activityIcon(type) {
    if (type === 'strength_training') return '◆';
    if (type === 'cycling') return '◇';
    return '↟';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function renderMonthlyChart(monthly) {
    const canvas = document.getElementById('monthlyChart');
    if (!canvas) return;
    if (_charts.monthly) _charts.monthly.destroy();
    _charts.monthly = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: monthly.map(m => m.month),
            datasets: [{
                label: '跑量 km',
                data: monthly.map(m => (m.distance / 1000).toFixed(1)),
                backgroundColor: monthly.map((_, i) => i === monthly.length - 1 ? '#e63f4f' : 'rgba(230, 63, 79, 0.52)'),
                hoverBackgroundColor: '#e63f4f',
                borderRadius: 5,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#edf0f4' }, ticks: { color: '#6b7785' } },
                x: { grid: { display: false }, ticks: { color: '#6b7785', maxRotation: 35, minRotation: 0 } }
            }
        }
    });
}

function renderPaceChart(paceDist) {
    const canvas = document.getElementById('paceChart');
    if (!canvas) return;
    if (_charts.pace) _charts.pace.destroy();
    
    // Format labels for display
    const labels = paceDist.map(p => zoneName(p.pace_range));
    const values = paceDist.map(p => p.count);
    const total = values.reduce((sum, n) => sum + Number(n || 0), 0);
    
    _charts.pace = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: ['#45a04a', '#3678e5', '#ff8a1f', '#e63f4f', '#6b7785', '#a7b0bd'],
                borderColor: '#ffffff',
                borderWidth: 3,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '58%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            const value = Number(ctx.raw || 0);
                            const pct = total ? Math.round(value / total * 100) : 0;
                            return ` ${ctx.label}: ${value.toFixed(1)} km (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
    
    // Render custom legend as table
    const legendContainer = canvas.parentElement.nextElementSibling;
    if (!legendContainer || !legendContainer.classList.contains('pace-legend')) return;
    
    const colors = ['#45a04a', '#3678e5', '#ff8a1f', '#e63f4f', '#6b7785', '#a7b0bd'];
    let html = '<table class="pace-table">';
    html += '<thead><tr><th>配速区间</th><th>距离</th><th>占比</th></tr></thead><tbody>';
    
    paceDist.forEach((p, i) => {
        const name = zoneName(p.pace_range);
        // Split name and pace range if VDOT format
        const parts = name.match(/^(.+?)\s+(\d+:\d+-\d+:\d+\/km)$/);
        const zoneNameStr = parts ? parts[1] : name;
        const paceRange = parts ? parts[2] : '';
        const pct = total ? Math.round(p.count / total * 100) : 0;
        
        html += `<tr>
            <td><span class="pace-dot" style="background:${colors[i]}"></span>${zoneNameStr}${paceRange ? `<span class="pace-range">${paceRange}</span>` : ''}</td>
            <td>${p.count.toFixed(1)} km</td>
            <td>${pct}%</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    legendContainer.innerHTML = html;
}

function renderHealthCards(data) {
    const el = document.getElementById('health-cards');
    if (!el) return;
    if (!data.length) {
        el.innerHTML = '<div class="empty-state" style="grid-column:1/-1">暂无健康数据，请在设置页同步。</div>';
        return;
    }

    let latest = null;
    let prev = null;
    for (let i = data.length - 1; i >= 0; i--) {
        const d = data[i];
        if (d.hrv_avg || d.sleep_score || d.resting_hr || d.avg_stress || d.body_battery_max) {
            if (!latest) latest = d;
            else if (!prev) { prev = d; break; }
        }
    }
    if (!latest) {
        el.innerHTML = '<div class="empty-state" style="grid-column:1/-1">健康数据同步中，请稍后查看。</div>';
        return;
    }

    function trend(curr, prevVal, unit) {
        if (!prevVal || !curr) return '';
        const diff = curr - prevVal;
        if (Math.abs(diff) < 0.5) return '';
        const cls = diff > 0 ? 'up' : 'down';
        return `<span class="trend-delta ${cls}">${diff > 0 ? '+' : ''}${Math.round(diff * 10) / 10}${unit}</span>`;
    }

    const cards = [];
    if (latest.sleep_score) cards.push(`<div class="stat-card"><div class="value">${latest.sleep_score}</div><div class="label">睡眠分数${trend(latest.sleep_score, prev?.sleep_score, '')}</div></div>`);
    if (latest.sleep_duration) cards.push(`<div class="stat-card"><div class="value">${latest.sleep_duration}h</div><div class="label">睡眠时长${trend(latest.sleep_duration, prev?.sleep_duration, 'h')}</div></div>`);
    if (latest.hrv_avg) cards.push(`<div class="stat-card"><div class="value">${Math.round(latest.hrv_avg)}</div><div class="label">HRV ms${trend(latest.hrv_avg, prev?.hrv_avg, '')}</div></div>`);
    if (latest.resting_hr) cards.push(`<div class="stat-card"><div class="value">${Math.round(latest.resting_hr)}</div><div class="label">静息心率${trend(latest.resting_hr, prev?.resting_hr, 'bpm')}</div></div>`);
    el.innerHTML = cards.join('') || '<div class="empty-state" style="grid-column:1/-1">暂无数据</div>';
}

function renderHealthChart(data) {
    const canvas = document.getElementById('healthChart');
    if (!canvas || !data.length) return;
    if (_charts.health) _charts.health.destroy();

    const labels = data.map(d => (d.date || '').slice(5));
    _charts.health = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: 'HRV ms', data: data.map(d => d.hrv_avg || null), borderColor: '#ff8a1f', backgroundColor: 'transparent', tension: 0.35, pointRadius: 2.5, borderWidth: 2.5, yAxisID: 'y' },
                { label: '睡眠分数', data: data.map(d => d.sleep_score || null), borderColor: '#3678e5', backgroundColor: 'transparent', tension: 0.35, pointRadius: 2.5, borderWidth: 2.5, yAxisID: 'y1' },
                { label: '静息心率 bpm', data: data.map(d => d.resting_hr || null), borderColor: '#45a04a', backgroundColor: 'transparent', tension: 0.35, pointRadius: 2.5, borderWidth: 2.5, yAxisID: 'y' },
                { label: '身体电量', data: data.map(d => d.body_battery_max || null), borderColor: '#e63f4f', backgroundColor: 'transparent', tension: 0.35, pointRadius: 2.5, borderWidth: 2.5, yAxisID: 'y1' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14, boxWidth: 10, color: '#59606d' } } },
            scales: {
                y: { type: 'linear', position: 'left', grid: { color: '#edf0f4' }, ticks: { color: '#6b7785' } },
                y1: { type: 'linear', position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { color: '#6b7785' } }
            }
        }
    });
}

function formatPace(seconds) {
    if (!seconds || seconds === 0) return '-';
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${String(sec).padStart(2, '0')}`;
}

let _charts = {};
