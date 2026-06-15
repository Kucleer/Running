registerPage('#report', (container) => {
    const today = new Date().toISOString().split('T')[0];
    const firstDayOfMonth = today.substring(0, 8) + '01';
    
    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">Report</div>
                <h1>训练报告</h1>
            </div>
        </div>
        <div class="report-filter">
            <input id="report-date-from" type="date" value="${firstDayOfMonth}">
            <span class="report-sep">-</span>
            <input id="report-date-to" type="date" value="${today}">
            <div class="report-quick-group">
                <button class="btn btn-secondary report-quick" data-range="week">近一周</button>
                <button class="btn btn-secondary report-quick" data-range="month">当月</button>
                <button class="btn btn-secondary report-quick" data-range="3month">近三个月</button>
                <button class="btn btn-secondary report-quick" data-range="halfYear">近半年</button>
                <button class="btn btn-secondary report-quick" data-range="year">当年</button>
            </div>
            <button class="btn" id="gen-report-btn" onclick="startReportGeneration()">开始生成</button>
        </div>
        <div class="dashboard-top-grid">
            <div class="card">
                <div class="section-title">
                    <h2>生成新报告</h2>
                </div>
                <div id="report-progress" style="margin-top:12px;display:none">
                    <div class="progress-bar"><div id="report-progress-fill" class="fill" style="width:0"></div></div>
                    <p id="report-status-text" class="muted small" style="margin-top:6px"></p>
                </div>
                <div class="empty-state" id="report-empty-tip">选择时间范围后生成训练报告。</div>
            </div>
            <div class="card">
                <div class="section-title"><h2>历史报告</h2></div>
                <div id="report-history"><div class="empty-state">加载中...</div></div>
            </div>
        </div>
        <div id="report-result" class="card" style="display:none">
            <div class="section-title">
                <h2>报告预览</h2>
                <button class="btn btn-secondary" onclick="printReport()">打印 / 保存 PDF</button>
            </div>
            <div id="report-content" class="report-md"></div>
        </div>
    `;

    // Quick filter buttons
    document.querySelectorAll('.report-quick').forEach(btn => {
        btn.onclick = () => {
            const range = btn.dataset.range;
            const today = new Date();
            let from;
            
            switch (range) {
                case 'week':
                    const weekAgo = new Date(today);
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    from = weekAgo.toISOString().split('T')[0];
                    break;
                case 'month':
                    from = today.toISOString().substring(0, 8) + '01';
                    break;
                case '3month':
                    const threeMonthsAgo = new Date(today);
                    threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);
                    from = threeMonthsAgo.toISOString().split('T')[0];
                    break;
                case 'halfYear':
                    const halfYearAgo = new Date(today);
                    halfYearAgo.setMonth(halfYearAgo.getMonth() - 6);
                    from = halfYearAgo.toISOString().split('T')[0];
                    break;
                case 'year':
                    from = today.getFullYear() + '-01-01';
                    break;
            }
            
            document.getElementById('report-date-from').value = from;
            document.getElementById('report-date-to').value = today.toISOString().split('T')[0];
        };
    });

    loadReportHistory();
});

async function loadReportHistory() {
    try {
        const reports = await API.listReports();
        const container = document.getElementById('report-history');
        if (!reports.length) {
            container.innerHTML = '<div class="empty-state">暂无历史报告</div>';
            return;
        }
        container.innerHTML = reports.map(r => `
            <div class="report-history-item">
                <div>
                    <div class="report-link" onclick="viewReport(${r.id})">${escHtml(r.title)}</div>
                    <div class="muted small">${r.date_from} ~ ${r.date_to} / ${r.created_at}</div>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="deleteReport(${r.id})">删除</button>
            </div>
        `).join('');
    } catch (err) {
        document.getElementById('report-history').innerHTML = `<div class="empty-state error-text">加载失败：${err.message}</div>`;
    }
}

async function viewReport(reportId) {
    try {
        const report = await API.getReport(reportId);
        document.getElementById('report-result').style.display = 'block';
        document.getElementById('report-content').innerHTML = marked.parse(report.content);
        window.scrollTo({ top: document.getElementById('report-result').offsetTop - 76, behavior: 'smooth' });
    } catch (err) {
        showToast('加载报告失败：' + err.message, 'error');
    }
}

async function deleteReport(reportId) {
    if (!confirm('确定删除这份报告？')) return;
    try {
        await API.deleteReport(reportId);
        loadReportHistory();
    } catch (err) {
        showToast('删除失败：' + err.message, 'error');
    }
}

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

async function startReportGeneration() {
    const btn = document.getElementById('gen-report-btn');
    btn.disabled = true;
    btn.textContent = '生成中...';

    const progressDiv = document.getElementById('report-progress');
    const progressFill = document.getElementById('report-progress-fill');
    const statusText = document.getElementById('report-status-text');
    const emptyTip = document.getElementById('report-empty-tip');
    progressDiv.style.display = 'block';
    if (emptyTip) emptyTip.style.display = 'none';
    statusText.style.color = '';
    document.getElementById('report-result').style.display = 'none';

    try {
        const body = {};
        const dateFrom = document.getElementById('report-date-from').value;
        const dateTo = document.getElementById('report-date-to').value;
        if (dateFrom) body.from = dateFrom;
        if (dateTo) body.to = dateTo;

        const { task_id } = await API.generateReport(body);
        let width = 0;
        const pollInterval = setInterval(async () => {
            try {
                const status = await API.reportStatus(task_id);
                statusText.textContent = status.progress;
                width = Math.min(width + 3, 90);
                progressFill.style.width = width + '%';

                if (status.status === 'done' || status.status === 'error') {
                    clearInterval(pollInterval);
                    if (status.status === 'done') {
                        progressFill.style.width = '100%';
                        const result = await API.reportResult(task_id);
                        document.getElementById('report-result').style.display = 'block';
                        document.getElementById('report-content').innerHTML = marked.parse(result.report);
                        loadReportHistory();
                    } else {
                        statusText.textContent = '报告生成失败';
                        statusText.style.color = '#d92d20';
                    }
                    btn.disabled = false;
                    btn.textContent = '开始生成';
                }
            } catch (e) {
                clearInterval(pollInterval);
                statusText.textContent = '获取状态失败：' + e.message;
                statusText.style.color = '#d92d20';
                btn.disabled = false;
                btn.textContent = '开始生成';
            }
        }, 2000);
    } catch (err) {
        statusText.textContent = '启动失败：' + err.message;
        statusText.style.color = '#d92d20';
        btn.disabled = false;
        btn.textContent = '开始生成';
    }
}

function printReport() {
    const content = document.getElementById('report-content').innerHTML;
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    printWindow.document.write(`
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>训练报告</title>
        <style>
            body { font-family: sans-serif; max-width: 800px; margin: 40px auto; line-height:1.7; }
            table { border-collapse:collapse; width:100%; }
            th,td { border:1px solid #ddd; padding:8px; }
            @media print { body { margin: 20px; } }
        </style></head>
        <body>${content}</body></html>
    `);
    printWindow.document.close();
    setTimeout(() => printWindow.print(), 500);
}
