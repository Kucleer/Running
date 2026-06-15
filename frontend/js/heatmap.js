let _heatmapMap = null;
let _heatmapLayer = null;

registerPage('#heatmap', async (container) => {
    const today = new Date().toISOString().split('T')[0];

    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">Route Heatmap</div>
                <h1>跑步热力图</h1>
            </div>
        </div>
        <div class="heatmap-filter">
            <div class="heatmap-filter-inner">
                <input id="heatmap-from" type="date">
                <span class="heatmap-sep">-</span>
                <input id="heatmap-to" type="date" value="${today}">
                <div class="heatmap-mode-group">
                    <button class="heatmap-mode-btn active" data-mode="distance">按里程</button>
                    <button class="heatmap-mode-btn" data-mode="count">按次数</button>
                    <button class="heatmap-mode-btn" data-mode="pace">按配速</button>
                </div>
                <div class="heatmap-quick-group">
                    <button class="btn btn-secondary heatmap-quick" data-days="30">近30天</button>
                    <button class="btn btn-secondary heatmap-quick" data-days="90">近3个月</button>
                    <button class="btn btn-secondary heatmap-quick" data-days="thisYear">今年</button>
                    <button class="btn btn-secondary heatmap-quick" data-days="all">全部</button>
                </div>
                <button class="btn" id="heatmap-apply">应用</button>
                <button class="btn btn-secondary btn-sm" id="heatmap-backfill" title="补采路线数据" style="margin-left:auto">补采</button>
            </div>
        </div>

        <div class="heatmap-map-wrapper">
            <div id="heatmap-map" class="heatmap-map"></div>
            
            <div id="heatmap-city-label" class="heatmap-city-label" style="display:none">
                <span id="city-name"></span>
            </div>

            <div id="heatmap-stats" class="heatmap-stats-overlay">
                <div class="heatmap-stat-item">
                    <div class="heatmap-stat-value" id="stat-cities">-</div>
                    <div class="heatmap-stat-label">覆盖城市</div>
                </div>
                <div class="heatmap-stat-item">
                    <div class="heatmap-stat-value" id="stat-distance">-</div>
                    <div class="heatmap-stat-label">总里程 km</div>
                </div>
                <div class="heatmap-stat-item">
                    <div class="heatmap-stat-value" id="stat-latest">-</div>
                    <div class="heatmap-stat-label">最近跑步</div>
                </div>
            </div>

            <div id="heatmap-routes" class="heatmap-routes-overlay">
                <div class="heatmap-routes-title">热门路线</div>
                <div id="heatmap-routes-list" class="heatmap-routes-list"></div>
            </div>
        </div>

        <div id="heatmap-empty" class="heatmap-empty" style="display:none">
            <div class="heatmap-empty-icon">🗺️</div>
            <div class="heatmap-empty-text">暂无路线数据</div>
            <div class="heatmap-empty-hint">请先点击「补采」按钮获取跑步路线数据</div>
        </div>
    `;

    // Quick filter buttons
    document.querySelectorAll('.heatmap-quick').forEach(btn => {
        btn.onclick = () => {
            const days = btn.dataset.days;
            const to = today;
            let from;
            if (days === 'all') {
                from = '2001-01-01';
            } else if (days === 'thisYear') {
                from = `${new Date().getFullYear()}-01-01`;
            } else {
                const d = new Date();
                d.setDate(d.getDate() - parseInt(days));
                from = d.toISOString().split('T')[0];
            }
            document.getElementById('heatmap-from').value = from;
            document.getElementById('heatmap-to').value = to;
            loadHeatmap();
        };
    });

    // Mode buttons
    document.querySelectorAll('.heatmap-mode-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.heatmap-mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadHeatmap();
        };
    });

    document.getElementById('heatmap-apply').onclick = loadHeatmap;
    document.getElementById('heatmap-backfill').onclick = backfillRoutes;

    // Default: all time
    document.getElementById('heatmap-from').value = '2001-01-01';

    // Initialize map
    initMap();
    loadHeatmap();
});

function initMap() {
    if (typeof AMap === 'undefined') {
        console.warn('AMap SDK not loaded');
        document.getElementById('heatmap-map').innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;height:100%;background:#f0f0f0;color:#999;font-size:14px">
                地图加载失败，请检查网络连接或刷新页面重试
            </div>
        `;
        return;
    }

    try {
        _heatmapMap = new AMap.Map('heatmap-map', {
            zoom: 12,
            center: [121.47, 31.23],
            mapStyle: 'amap://styles/light',
            viewMode: '2D',
            zooms: [3, 18],
        });

        // Add zoom control
        AMap.plugin('AMap.ToolBar', function() {
            _heatmapMap.addControl(new AMap.ToolBar({
                position: 'LT',
                liteStyle: true,
            }));
        });

        // Add scale control
        AMap.plugin('AMap.Scale', function() {
            _heatmapMap.addControl(new AMap.Scale());
        });

    } catch (e) {
        console.error('Map init error:', e);
    }
}

async function loadHeatmap() {
    const from = document.getElementById('heatmap-from').value;
    const to = document.getElementById('heatmap-to').value;
    const modeBtn = document.querySelector('.heatmap-mode-btn.active');
    const mode = modeBtn ? modeBtn.dataset.mode : 'distance';

    try {
        const resp = await fetch(`/api/heatmap?from=${from}&to=${to}&mode=${mode}`);
        const data = await resp.json();

        if (data.error) {
            showHeatmapEmpty();
            return;
        }

        updateStats(data.summary);
        updateHotRoutes(data.hot_routes);
        updateCityLabel(data.default_city);

        if (!data.points || data.points.length === 0) {
            showHeatmapEmpty();
            return;
        }

        hideHeatmapEmpty();
        updateMap(data);
    } catch (err) {
        console.error('Heatmap load error:', err);
        showHeatmapEmpty();
    }
}

function updateStats(summary) {
    if (!summary) return;
    document.getElementById('stat-cities').textContent = summary.cities || 0;
    document.getElementById('stat-distance').textContent = (summary.distance_km || 0).toFixed(1);
    document.getElementById('stat-latest').textContent = summary.latest_activity || '-';
}

function updateCityLabel(city) {
    const el = document.getElementById('heatmap-city-label');
    const nameEl = document.getElementById('city-name');
    if (city) {
        nameEl.textContent = city;
        el.style.display = 'flex';
    } else {
        el.style.display = 'none';
    }
}

function updateHotRoutes(routes) {
    const el = document.getElementById('heatmap-routes-list');
    if (!el) return;

    if (!routes || routes.length === 0) {
        el.innerHTML = '<div class="heatmap-routes-empty">暂无热门路线</div>';
        return;
    }

    el.innerHTML = routes.map((r, i) => `
        <div class="heatmap-route-item">
            <div class="heatmap-route-rank">${i + 1}</div>
            <div class="heatmap-route-info">
                <span class="heatmap-route-area">${escapeHtml(r.area)}</span>
                <span class="heatmap-route-meta">${r.count}次 · ${r.distance_km}km · ${r.avg_pace}</span>
                <span class="heatmap-route-date">${r.latest_activity}</span>
            </div>
        </div>
    `).join('');
}

function updateMap(data) {
    if (!_heatmapMap || typeof AMap === 'undefined') {
        console.warn('Map not available');
        return;
    }

    // Clear existing markers
    _heatmapMap.clearMap();
    _heatmapLayer = null;

    // Set center and zoom
    if (data.center) {
        _heatmapMap.setCenter([data.center.lng, data.center.lat]);
    }

    if (data.bounds) {
        try {
            const sw = new AMap.LngLat(data.bounds.min_lng, data.bounds.min_lat);
            const ne = new AMap.LngLat(data.bounds.max_lng, data.bounds.max_lat);
            const bounds = new AMap.Bounds(sw, ne);
            _heatmapMap.setBounds(bounds, [80, 80, 80, 80]);
        } catch (e) {
            console.warn('Set bounds error:', e);
        }
    }

    // Group nearby points and calculate density
    const gridSize = 0.002;
    const grid = {};
    for (const p of data.points) {
        const key = `${Math.round(p.lat / gridSize)}_${Math.round(p.lng / gridSize)}`;
        if (!grid[key]) {
            grid[key] = { lat: 0, lng: 0, count: 0, weight: 0 };
        }
        grid[key].lat += p.lat;
        grid[key].lng += p.lng;
        grid[key].count += 1;
        grid[key].weight += (p.weight || 1);
    }

    const clusters = Object.values(grid).map(g => ({
        lat: g.lat / g.count,
        lng: g.lng / g.count,
        count: g.count,
        weight: g.weight / g.count,
    }));

    const maxCount = Math.max(1, ...clusters.map(c => c.count));

    // Create circle markers with size and color based on density
    const markers = clusters.map(c => {
        const ratio = c.count / maxCount;
        const radius = 3 + ratio * 18;
        const opacity = 0.4 + ratio * 0.5;

        // Color: blue (low) -> green (mid) -> orange/red (high)
        let color;
        if (ratio < 0.3) {
            color = `rgba(66, 133, 244, ${opacity})`; // Blue
        } else if (ratio < 0.6) {
            color = `rgba(52, 168, 83, ${opacity})`; // Green
        } else if (ratio < 0.8) {
            color = `rgba(251, 188, 4, ${opacity})`; // Yellow
        } else {
            color = `rgba(234, 67, 53, ${opacity})`; // Red
        }

        return new AMap.CircleMarker({
            center: [c.lng, c.lat],
            radius: radius,
            strokeColor: color,
            strokeWeight: 1,
            strokeOpacity: 0.6,
            fillColor: color,
            fillOpacity: opacity,
            cursor: 'pointer',
            bubble: true,
        });
    });

    _heatmapMap.add(markers);
}

function showHeatmapEmpty() {
    document.getElementById('heatmap-empty').style.display = 'flex';
    document.querySelector('.heatmap-map-wrapper').style.display = 'none';
}

function hideHeatmapEmpty() {
    document.getElementById('heatmap-empty').style.display = 'none';
    document.querySelector('.heatmap-map-wrapper').style.display = 'block';
}

async function backfillRoutes() {
    const btn = document.getElementById('heatmap-backfill');
    btn.disabled = true;
    btn.textContent = '补采中...';

    try {
        const resp = await fetch('/api/heatmap/backfill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limit: 1000 }),
        });
        const result = await resp.json();

        if (result.error) {
            alert('补采失败: ' + result.error);
        } else {
            alert(`补采完成: 成功获取 ${result.filled} 条路线，共检查 ${result.total} 条活动`);
            loadHeatmap();
        }
    } catch (err) {
        alert('补采失败: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '补采';
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
