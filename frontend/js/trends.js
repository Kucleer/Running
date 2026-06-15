let _trendsCharts = {};

registerPage('#trends', async (container) => {
    const today = new Date().toISOString().split('T')[0];

    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">Training Trends</div>
                <h1>训练趋势</h1>
            </div>
        </div>
        <div class="trends-filter">
            <input id="trends-from" type="date">
            <span class="trends-sep">-</span>
            <input id="trends-to" type="date" value="${today}">
            <div class="trends-bucket-group">
                <button class="trends-bucket-btn active" data-bucket="week">周</button>
                <button class="trends-bucket-btn" data-bucket="day">天</button>
                <button class="trends-bucket-btn" data-bucket="month">月</button>
            </div>
            <div class="trends-quick-group">
                <button class="btn btn-secondary trends-quick" data-days="30">近30天</button>
                <button class="btn btn-secondary trends-quick" data-days="90">近3个月</button>
                <button class="btn btn-secondary trends-quick" data-days="thisYear">今年</button>
                <button class="btn btn-secondary trends-quick" data-days="all">全部</button>
            </div>
            <button class="btn" id="trends-apply">应用</button>
        </div>

        <div id="trends-kpi" class="trends-kpi-grid"></div>

        <div class="trends-charts-grid">
            <div class="card">
                <div class="section-title"><h2>跑力趋势</h2></div>
                <div class="chart-wrap"><canvas id="vdotTrendChart"></canvas></div>
            </div>
            <div class="card">
                <div class="section-title"><h2>跑量趋势</h2></div>
                <div class="chart-wrap"><canvas id="volumeTrendChart"></canvas></div>
            </div>
            <div class="card">
                <div class="section-title"><h2>配速 / 心率趋势</h2></div>
                <div class="chart-wrap"><canvas id="paceHrChart"></canvas></div>
            </div>
            <div class="card">
                <div class="section-title"><h2>恢复趋势</h2></div>
                <div class="chart-wrap"><canvas id="recoveryChart"></canvas></div>
            </div>
        </div>

        <div class="card">
            <div class="section-title"><h2>周期汇总</h2></div>
            <div id="trends-summary-table" class="table-wrap"></div>
        </div>
    `;

    // Bucket segmented controls
    document.querySelectorAll('.trends-bucket-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.trends-bucket-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        };
    });

    // Quick filter buttons
    document.querySelectorAll('.trends-quick').forEach(btn => {
        btn.onclick = () => {
            const days = btn.dataset.days;
            const to = today;
            let from;
            if (days === 'all') {
                from = '1970-01-01';
            } else if (days === 'thisYear') {
                from = `${new Date().getFullYear()}-01-01`;
            } else {
                const d = new Date();
                d.setDate(d.getDate() - parseInt(days));
                from = d.toISOString().split('T')[0];
            }
            document.getElementById('trends-from').value = from;
            document.getElementById('trends-to').value = to;
            loadTrends();
        };
    });

    document.getElementById('trends-apply').onclick = loadTrends;

    // Default: last 90 days
    const d90 = new Date();
    d90.setDate(d90.getDate() - 90);
    document.getElementById('trends-from').value = d90.toISOString().split('T')[0];

    loadTrends();
});

async function loadTrends() {
    const from = document.getElementById('trends-from').value;
    const to = document.getElementById('trends-to').value;
    const bucketBtn = document.querySelector('.trends-bucket-btn.active');
    const bucket = bucketBtn ? bucketBtn.dataset.bucket : 'week';

    try {
        const resp = await fetch(`/api/trends?from=${from}&to=${to}&bucket=${bucket}`);
        const data = await resp.json();

        renderTrendsKPI(data.summary);
        renderVdotTrend(data.series);
        renderVolumeTrend(data.series);
        renderPaceHrTrend(data.series);
        renderRecoveryTrend(data.series);
        renderSummaryTable(data.series, bucket);
    } catch (err) {
        console.error('Trends load error:', err);
    }
}

function renderTrendsKPI(summary) {
    const el = document.getElementById('trends-kpi');
    if (!el) return;

    const recoveryValue = summary.recovery_index ?? '-';
    const recoveryUnit = summary.recovery_unit ?? '';

    // Show Garmin VO2max if available, otherwise show estimate
    const vo2maxDisplay = summary.garmin_vo2max ?? summary.vo2max_estimate ?? '-';
    const vo2maxLabel = summary.garmin_vo2max ? 'Garmin VO2max' : 'VO2max 估算';

    el.innerHTML = [
        kpiCard('V', summary.vdot ?? '-', '当前 VDOT', '', '#e63f4f'),
        kpiCard('O', vo2maxDisplay, vo2maxLabel, '', '#3678e5'),
        kpiCard('W', summary.weekly_avg ?? '-', '周均跑量', 'km', '#45a04a'),
        kpiCard('⇄', formatPace(summary.avg_pace), '平均配速', '/km', '#ff8a1f'),
        kpiCard('♡', summary.avg_hr ? Math.round(summary.avg_hr) : '-', '平均心率', 'bpm', '#e63f4f'),
        kpiCard('↻', recoveryValue, '恢复指数', recoveryUnit, '#3678e5'),
    ].join('');
}

function kpiCard(icon, value, label, unit, color) {
    return `
        <div class="stat-card trends-kpi-card">
            <div class="trends-kpi-icon" style="color:${color}">${icon}</div>
            <div class="trends-kpi-body">
                <div class="label">${label}</div>
                <div class="value">${value ?? '-'}<span class="metric-unit">${unit ? ' ' + unit : ''}</span></div>
            </div>
        </div>
    `;
}

function renderVdotTrend(series) {
    const canvas = document.getElementById('vdotTrendChart');
    if (!canvas) return;
    if (_trendsCharts.vdot) _trendsCharts.vdot.destroy();

    const labels = series.map(s => s.period);
    const vdotData = series.map(s => s.vdot);
    const vo2Data = series.map(s => s.vo2max_estimate);
    const garminData = series.map(s => s.garmin_vo2max);

    const hasGarmin = garminData.some(v => v != null);

    const datasets = [
        {
            label: 'VDOT',
            data: vdotData,
            borderColor: '#e63f4f',
            backgroundColor: 'rgba(230,63,79,0.06)',
            fill: true,
            tension: 0.35,
            pointRadius: 4,
            pointBackgroundColor: '#e63f4f',
            borderWidth: 2.5,
            spanGaps: true,
        },
        {
            label: 'VO2max 估算',
            data: vo2Data,
            borderColor: '#3678e5',
            backgroundColor: 'transparent',
            tension: 0.35,
            pointRadius: 4,
            pointBackgroundColor: '#3678e5',
            borderWidth: 2,
            borderDash: [8, 4],
            spanGaps: true,
            pointStyle: 'rectRot',
        },
    ];

    if (hasGarmin) {
        datasets.push({
            label: 'Garmin VO2max',
            data: garminData,
            borderColor: '#45a04a',
            backgroundColor: 'transparent',
            tension: 0.35,
            pointRadius: 3,
            borderWidth: 2,
            borderDash: [3, 3],
            spanGaps: true,
        });
    }

    _trendsCharts.vdot = new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14, boxWidth: 10, color: '#59606d' } },
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            const label = ctx.dataset.label;
                            const val = ctx.raw;
                            if (val == null) return ` ${label}: 无数据`;
                            return ` ${label}: ${val.toFixed(1)}`;
                        }
                    }
                },
            },
            scales: {
                y: {
                    position: 'left',
                    grid: { color: '#edf0f4' },
                    ticks: { color: '#6b7785' },
                    title: { display: false },
                },
                x: { grid: { display: false }, ticks: { color: '#6b7785', maxRotation: 35 } },
            },
        },
    });
}

function renderVolumeTrend(series) {
    const canvas = document.getElementById('volumeTrendChart');
    if (!canvas) return;
    if (_trendsCharts.volume) _trendsCharts.volume.destroy();

    const labels = series.map(s => s.period);

    _trendsCharts.volume = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: '跑量 km',
                    data: series.map(s => (s.total_distance / 1000).toFixed(1)),
                    backgroundColor: 'rgba(230,63,79,0.55)',
                    hoverBackgroundColor: '#e63f4f',
                    borderRadius: 4,
                    borderSkipped: false,
                    yAxisID: 'y',
                },
                {
                    label: '跑步次数',
                    data: series.map(s => s.count),
                    type: 'line',
                    borderColor: '#3678e5',
                    backgroundColor: 'transparent',
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#3678e5',
                    borderWidth: 2.5,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14, boxWidth: 10, color: '#59606d' } } },
            scales: {
                y: { beginAtZero: true, position: 'left', grid: { color: '#edf0f4' }, ticks: { color: '#6b7785' }, title: { display: true, text: 'km', color: '#6b7785' } },
                y1: { beginAtZero: true, position: 'right', grid: { display: false }, ticks: { color: '#6b7785', stepSize: 1 }, title: { display: true, text: '次', color: '#6b7785' } },
                x: { grid: { display: false }, ticks: { color: '#6b7785', maxRotation: 35 } },
            },
        },
    });
}

function renderPaceHrTrend(series) {
    const canvas = document.getElementById('paceHrChart');
    if (!canvas) return;
    if (_trendsCharts.paceHr) _trendsCharts.paceHr.destroy();

    const labels = series.map(s => s.period);
    const paceData = series.map(s => s.avg_pace);
    const hrData = series.map(s => s.avg_hr);

    _trendsCharts.paceHr = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: '配速 s/km',
                    data: paceData,
                    borderColor: '#e63f4f',
                    backgroundColor: 'transparent',
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#e63f4f',
                    borderWidth: 2.5,
                    spanGaps: true,
                    yAxisID: 'y',
                },
                {
                    label: '心率 bpm',
                    data: hrData,
                    borderColor: '#3678e5',
                    backgroundColor: 'transparent',
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#3678e5',
                    borderWidth: 2.5,
                    spanGaps: true,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14, boxWidth: 10, color: '#59606d' } },
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            if (ctx.dataset.label.includes('配速')) {
                                return ` 配速: ${formatPace(ctx.raw)}/km`;
                            }
                            return ` 心率: ${Math.round(ctx.raw)} bpm`;
                        }
                    }
                },
            },
            scales: {
                y: {
                    position: 'left',
                    reverse: true,
                    grid: { color: '#edf0f4' },
                    ticks: {
                        color: '#6b7785',
                        callback(v) { return formatPace(v); },
                    },
                    title: { display: false },
                },
                y1: { position: 'right', grid: { display: false }, ticks: { color: '#6b7785' }, title: { display: false } },
                x: { grid: { display: false }, ticks: { color: '#6b7785', maxRotation: 35 } },
            },
        },
    });
}

function renderRecoveryTrend(series) {
    const canvas = document.getElementById('recoveryChart');
    if (!canvas) return;
    if (_trendsCharts.recovery) _trendsCharts.recovery.destroy();

    const labels = series.map(s => s.period);
    const hrvData = series.map(s => s.hrv_avg);
    const sleepData = series.map(s => s.sleep_score);
    const rhrData = series.map(s => s.resting_hr);

    const hasData = hrvData.some(v => v != null) || sleepData.some(v => v != null) || rhrData.some(v => v != null);

    if (!hasData) {
        const wrap = canvas.parentElement;
        wrap.innerHTML = '<div class="empty-state" style="padding:60px 0;text-align:center;color:#999">暂无健康数据，请在设置页同步健康数据</div>';
        return;
    }

    _trendsCharts.recovery = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'HRV ms',
                    data: hrvData,
                    borderColor: '#ff8a1f',
                    backgroundColor: 'transparent',
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#ff8a1f',
                    borderWidth: 2.5,
                    spanGaps: true,
                    yAxisID: 'y',
                },
                {
                    label: '睡眠分数',
                    data: sleepData,
                    borderColor: '#3678e5',
                    backgroundColor: 'transparent',
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#3678e5',
                    borderWidth: 2.5,
                    spanGaps: true,
                    yAxisID: 'y1',
                },
                {
                    label: '静息心率',
                    data: rhrData,
                    borderColor: '#45a04a',
                    backgroundColor: 'transparent',
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: '#45a04a',
                    borderWidth: 2.5,
                    spanGaps: true,
                    yAxisID: 'y',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14, boxWidth: 10, color: '#59606d' } } },
            scales: {
                y: { position: 'left', grid: { color: '#edf0f4' }, ticks: { color: '#6b7785' }, title: { display: false } },
                y1: { position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { color: '#6b7785' }, title: { display: false } },
                x: { grid: { display: false }, ticks: { color: '#6b7785', maxRotation: 35 } },
            },
        },
    });
}

function renderSummaryTable(series, bucket) {
    const el = document.getElementById('trends-summary-table');
    if (!el) return;

    if (!series.length) {
        el.innerHTML = '<div class="empty-state">暂无数据</div>';
        return;
    }

    const bucketLabel = { day: '日期', week: '周起始', month: '月份' }[bucket] || '周期';

    // Reverse to show newest first
    const reversedSeries = [...series].reverse();

    const rows = reversedSeries.map(s => {
        const recovery = s.recovery_score != null ? `${s.recovery_score}${s.recovery_unit || ''}` : '-';
        return `
            <tr>
                <td>${s.period}</td>
                <td>${(s.total_distance / 1000).toFixed(1)} km</td>
                <td>${s.count}</td>
                <td>${formatPace(s.avg_pace)}/km</td>
                <td>${s.avg_hr ? Math.round(s.avg_hr) : '-'}</td>
                <td>${s.vdot ?? '-'}</td>
                <td>${s.vo2max_estimate ?? '-'}</td>
                <td>${recovery}</td>
            </tr>
        `;
    }).join('');

    el.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>${bucketLabel}</th>
                    <th>跑量</th>
                    <th>次数</th>
                    <th>平均配速</th>
                    <th>平均心率</th>
                    <th>VDOT</th>
                    <th>VO2max</th>
                    <th>恢复指标</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

function formatPace(seconds) {
    if (!seconds || seconds <= 0) return '-';
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${String(sec).padStart(2, '0')}`;
}
