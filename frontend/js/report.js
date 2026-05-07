registerPage('#report', (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">AI 训练报告</h1>
        <div class="card">
            <div class="flex-between">
                <h2>生成新报告</h2>
                <button class="btn" id="gen-report-btn" onclick="startReportGeneration()">开始生成</button>
            </div>
            <div style="margin-top:12px;display:flex;gap:12px">
                <div><label>开始日期</label><input id="report-date-from" type="date"></div>
                <div><label>结束日期</label><input id="report-date-to" type="date"></div>
            </div>
            <div id="report-progress" style="margin-top:12px;display:none">
                <div class="progress-bar"><div id="report-progress-fill" class="fill" style="width:0"></div></div>
                <p id="report-status-text" style="font-size:13px;color:#888;margin-top:4px"></p>
            </div>
        </div>
        <div id="report-result" class="card" style="display:none">
            <div class="flex-between">
                <h2>训练报告</h2>
                <button class="btn btn-secondary" onclick="printReport()">打印 / 保存 PDF</button>
            </div>
            <div id="report-content" class="report-md"></div>
        </div>
        <div class="card" style="margin-top:16px">
            <h2>历史报告</h2>
            <div id="report-history"><p style="color:var(--text-muted)">加载中...</p></div>
        </div>
    `;

    loadReportHistory();
});

async function loadReportHistory() {
    try {
        const reports = await API.listReports();
        const container = document.getElementById('report-history');
        if (!reports.length) {
            container.innerHTML = '<p style="color:var(--text-muted)">暂无历史报告</p>';
            return;
        }
        container.innerHTML = reports.map(r => `
            <div class="report-history-item">
                <div>
                    <strong style="cursor:pointer;color:var(--primary)" onclick="viewReport(${r.id})">${escHtml(r.title)}</strong>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${r.date_from} ~ ${r.date_to} | ${r.created_at}</div>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="deleteReport(${r.id})">删除</button>
            </div>
        `).join('');
    } catch (err) {
        document.getElementById('report-history').innerHTML = `<p style="color:red">加载失败: ${err.message}</p>`;
    }
}

async function viewReport(reportId) {
    try {
        const report = await API.getReport(reportId);
        document.getElementById('report-result').style.display = 'block';
        document.getElementById('report-content').innerHTML = marked.parse(report.content);
        window.scrollTo({ top: document.getElementById('report-result').offsetTop - 20, behavior: 'smooth' });
    } catch (err) {
        showToast('加载报告失败: ' + err.message, 'error');
    }
}

async function deleteReport(reportId) {
    if (!confirm('确定删除这份报告？')) return;
    try {
        await API.deleteReport(reportId);
        loadReportHistory();
    } catch (err) {
        showToast('删除失败: ' + err.message, 'error');
    }
}

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

async function startReportGeneration() {
    const btn = document.getElementById('gen-report-btn');
    btn.disabled = true;
    btn.textContent = '生成中...';

    const progressDiv = document.getElementById('report-progress');
    const progressFill = document.getElementById('report-progress-fill');
    const statusText = document.getElementById('report-status-text');
    progressDiv.style.display = 'block';

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
                    } else {
                        statusText.textContent = '报告生成失败';
                        statusText.style.color = 'red';
                    }
                    btn.disabled = false;
                    btn.textContent = '开始生成';
                }
            } catch (e) {
                clearInterval(pollInterval);
                statusText.textContent = '获取状态失败: ' + e.message;
                btn.disabled = false;
                btn.textContent = '开始生成';
            }
        }, 2000);
    } catch (err) {
        statusText.textContent = '启动失败: ' + err.message;
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
