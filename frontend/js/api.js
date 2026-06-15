const API = {
    async request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(path, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: resp.statusText }));
            throw new Error(err.error || 'Request failed');
        }
        return resp.json();
    },

    get(path) { return this.request('GET', path); },
    post(path, body) { return this.request('POST', path, body); },
    delete(path) { return this.request('DELETE', path); },

    activities(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return this.get('/api/activities' + (qs ? '?' + qs : ''));
    },
    activityDetail(id) { return this.get('/api/activity/' + id); },
    activitySplits(id) { return this.get('/api/activities/' + id + '/splits'); },

    sync(email, password, syncHealth = true, healthDays = 14) { return this.post('/api/sync', { email, password, sync_health: syncHealth, health_days: healthDays }); },
    backfillDetails(limit = 0) { return this.post('/api/sync/backfill', limit ? { limit } : { all: true }); },
    backfillWeather(limit = 50) { return this.post('/api/sync/backfill_weather', { limit }); },
    healthData(days = 14, from = null, to = null) {
        if (from && to) {
            return this.get(`/api/health?from=${from}&to=${to}`);
        }
        return this.get('/api/health?days=' + days);
    },
    healthSync(days = 7) { return this.post('/api/health/sync', { days }); },

    stats(period = 'monthly', dateFrom = null, dateTo = null) {
        const qs = new URLSearchParams({ period });
        if (dateFrom) qs.set('from', dateFrom);
        if (dateTo) qs.set('to', dateTo);
        return this.get('/api/stats?' + qs.toString());
    },
    vdot() { return this.get('/api/vdot'); },

    generateReport(body) { return this.post('/api/report/generate', body); },
    reportStatus(taskId) { return this.get('/api/report/status/' + taskId); },
    reportResult(taskId) { return this.get('/api/report/result/' + taskId); },
    listReports() { return this.get('/api/reports'); },
    getReport(id) { return this.get('/api/report/' + id); },
    deleteReport(id) { return this.delete('/api/report/' + id); },

    async chatAsk(question, sessionId, onChunk, includeStrength = false) {
        const resp = await fetch('/api/chat/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, session_id: sessionId, include_strength: includeStrength })
        });
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = decoder.decode(value, { stream: true });
            const lines = text.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') return;
                    let parsed = data;
                    try {
                        parsed = JSON.parse(data);
                    } catch {
                    }
                    onChunk(parsed);
                }
            }
        }
    },
    chatHistory(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return this.get('/api/chat/history' + (qs ? '?' + qs : ''));
    },
    chatDelete(id) { return this.delete('/api/chat/delete/' + id); },
    chatClear() { return this.delete('/api/chat/clear'); },
    chatSessions() { return this.get('/api/chat/sessions'); },
    chatCreateSession() { return this.post('/api/chat/sessions'); },
    chatDeleteSession(id) { return this.delete('/api/chat/sessions/' + id); },

    getConfig() { return this.get('/api/config'); },
    updateConfig(data) { return this.post('/api/config', data); }
};
