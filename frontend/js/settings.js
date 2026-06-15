registerPage('#settings', async (container) => {
    container.innerHTML = `
        <div class="page-header">
            <div>
                <div class="page-kicker">Settings</div>
                <h1>设置</h1>
            </div>
        </div>
        <div class="dashboard-top-grid">
            <div class="card">
                <div class="section-title"><h2>LLM 配置</h2></div>
                <div class="form-panel">
                    <label>API 地址</label>
                    <input id="cfg-base-url" type="text" placeholder="https://api.deepseek.com/v1">
                    <label>API Key</label>
                    <input id="cfg-api-key" type="password" placeholder="sk-...">
                    <label>模型名称</label>
                    <input id="cfg-model" type="text" placeholder="deepseek-chat">
                    <label>报告生成轮数 3-5</label>
                    <input id="cfg-rounds" type="number" min="3" max="5" value="4">
                    <button class="btn" id="cfg-save-btn">保存配置</button>
                    <p id="cfg-msg" class="small" style="margin-top:8px"></p>
                </div>
            </div>

            <div class="card">
                <div class="section-title"><h2>天气与位置</h2></div>
                <div class="form-panel">
                    <label>所在城市（用于AI问答天气信息）</label>
                    <select id="cfg-city">
                        <option value="上海市">上海市</option>
                        <option value="北京市">北京市</option>
                        <option value="广州市">广州市</option>
                        <option value="深圳市">深圳市</option>
                        <option value="杭州市">杭州市</option>
                        <option value="成都市">成都市</option>
                        <option value="武汉市">武汉市</option>
                        <option value="南京市">南京市</option>
                        <option value="重庆市">重庆市</option>
                        <option value="西安市">西安市</option>
                        <option value="苏州市">苏州市</option>
                        <option value="天津市">天津市</option>
                        <option value="长沙市">长沙市</option>
                        <option value="郑州市">郑州市</option>
                        <option value="青岛市">青岛市</option>
                        <option value="嘉兴市">嘉兴市</option>
                        <option value="宁波市">宁波市</option>
                        <option value="温州市">温州市</option>
                        <option value="合肥市">合肥市</option>
                        <option value="福州市">福州市</option>
                        <option value="厦门市">厦门市</option>
                        <option value="昆明市">昆明市</option>
                        <option value="贵阳市">贵阳市</option>
                        <option value="南昌市">南昌市</option>
                        <option value="济南市">济南市</option>
                        <option value="大连市">大连市</option>
                        <option value="哈尔滨市">哈尔滨市</option>
                        <option value="沈阳市">沈阳市</option>
                        <option value="长春市">长春市</option>
                    </select>
                    <button class="btn" id="city-save-btn">保存位置</button>
                    <p id="city-msg" class="small" style="margin-top:8px"></p>
                </div>
            </div>
        </div>

        <div class="dashboard-top-grid">
            <div class="card">
                <div class="section-title"><h2>Garmin 同步</h2></div>
                <div class="form-panel">
                    <label>邮箱</label>
                    <input id="sync-email" type="email" placeholder="your@email.com">
                    <label>密码</label>
                    <input id="sync-password" type="password" placeholder="仅本地传输，不保存密码">
                    <div class="button-row">
                        <button class="btn" id="sync-btn">同步数据</button>
                        <button class="btn btn-secondary" id="backfill-btn">补采活动详情</button>
                        <button class="btn btn-secondary" id="health-sync-btn">同步健康数据</button>
                        <button class="btn btn-secondary" id="weather-backfill-btn">补采天气数据</button>
                    </div>
                    <div id="sync-progress" style="margin-top:12px;display:none">
                        <div class="progress-bar"><div id="sync-progress-fill" class="fill" style="width:0"></div></div>
                        <p id="sync-status-text" class="muted small" style="margin-top:6px"></p>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="section-title"><h2>跑者基础信息</h2></div>
                <div class="form-panel">
                    <div class="form-grid">
                        <div><label>年龄</label><input id="profile-age" type="number" min="1" max="120" placeholder="28"></div>
                        <div><label>性别</label><select id="profile-gender"><option value="">请选择</option><option value="male">男</option><option value="female">女</option></select></div>
                        <div><label>身高 cm</label><input id="profile-height" type="number" min="50" max="250" placeholder="170"></div>
                        <div><label>体重 kg</label><input id="profile-weight" type="number" min="20" max="300" placeholder="65"></div>
                        <div><label>静息心率</label><input id="profile-resting-hr" type="number" min="30" max="120" placeholder="55"></div>
                        <div><label>最大心率</label><input id="profile-max-hr" type="number" min="80" max="250" placeholder="190"></div>
                    </div>
                    <label>跑步目标</label>
                    <select id="profile-race-goal">
                        <option value="">请选择</option>
                        <option value="5k">5K</option>
                        <option value="10k">10K</option>
                        <option value="half_marathon">半马 21.1K</option>
                        <option value="marathon">全马 42.2K</option>
                    </select>
                    <button class="btn" id="profile-save-btn">保存信息</button>
                    <p id="profile-msg" class="small" style="margin-top:8px"></p>
                </div>
            </div>
        </div>
    `;

    try {
        const cfg = await API.getConfig();
        document.getElementById('cfg-base-url').value = cfg.llm_base_url || '';
        document.getElementById('cfg-api-key').value = cfg.llm_api_key || '';
        document.getElementById('cfg-model').value = cfg.llm_model || '';
        document.getElementById('cfg-rounds').value = cfg.report_rounds || '4';
        document.getElementById('cfg-city').value = cfg.weather_city || '上海市';

        document.getElementById('profile-age').value = cfg.profile_age || '';
        document.getElementById('profile-gender').value = cfg.profile_gender || '';
        document.getElementById('profile-height').value = cfg.profile_height || '';
        document.getElementById('profile-weight').value = cfg.profile_weight || '';
        document.getElementById('profile-resting-hr').value = cfg.profile_resting_hr || '';
        document.getElementById('profile-max-hr').value = cfg.profile_max_hr || '';
        document.getElementById('profile-race-goal').value = cfg.profile_race_goal || '';
    } catch (err) {
    }

    document.getElementById('cfg-save-btn').onclick = async () => {
        const btn = document.getElementById('cfg-save-btn');
        const msg = document.getElementById('cfg-msg');
        btn.disabled = true;
        try {
            await API.updateConfig({
                llm_base_url: document.getElementById('cfg-base-url').value,
                llm_api_key: document.getElementById('cfg-api-key').value,
                llm_model: document.getElementById('cfg-model').value,
                report_rounds: document.getElementById('cfg-rounds').value,
            });
            msg.textContent = '配置已保存';
            msg.className = 'small success-text';
        } catch (err) {
            msg.textContent = '保存失败：' + err.message;
            msg.className = 'small error-text';
        } finally {
            btn.disabled = false;
        }
    };

    document.getElementById('city-save-btn').onclick = async () => {
        const btn = document.getElementById('city-save-btn');
        const msg = document.getElementById('city-msg');
        btn.disabled = true;
        try {
            await API.updateConfig({
                weather_city: document.getElementById('cfg-city').value,
            });
            msg.textContent = '位置已保存';
            msg.className = 'small success-text';
        } catch (err) {
            msg.textContent = '保存失败：' + err.message;
            msg.className = 'small error-text';
        } finally {
            btn.disabled = false;
        }
    };

    document.getElementById('profile-save-btn').onclick = async () => {
        const btn = document.getElementById('profile-save-btn');
        const msg = document.getElementById('profile-msg');
        btn.disabled = true;
        try {
            await API.updateConfig({
                profile_age: document.getElementById('profile-age').value,
                profile_gender: document.getElementById('profile-gender').value,
                profile_height: document.getElementById('profile-height').value,
                profile_weight: document.getElementById('profile-weight').value,
                profile_resting_hr: document.getElementById('profile-resting-hr').value,
                profile_max_hr: document.getElementById('profile-max-hr').value,
                profile_race_goal: document.getElementById('profile-race-goal').value,
            });
            msg.textContent = '跑者信息已保存';
            msg.className = 'small success-text';
        } catch (err) {
            msg.textContent = '保存失败：' + err.message;
            msg.className = 'small error-text';
        } finally {
            btn.disabled = false;
        }
    };

    document.getElementById('sync-btn').onclick = async () => {
        const btn = document.getElementById('sync-btn');
        const email = document.getElementById('sync-email').value.trim();
        const password = document.getElementById('sync-password').value;
        if (!email || !password) {
            showToast('请输入邮箱和密码', 'error');
            return;
        }
        btn.disabled = true;
        btn.textContent = '同步中...';
        showProgress('正在连接 Garmin 服务...', '20%');
        try {
            const result = await API.sync(email, password);
            let msg = `同步完成，共检查 ${result.total_checked} 条活动`;
            if (result.new_count > 0) {
                msg += `，新增 ${result.new_count} 条`;
                showProgress(msg + '，正在获取详情...', '60%');
                msg += `，已获取 ${result.detail_count} 条详情`;
            }
            if (result.health_fetched > 0) {
                msg += `，健康数据 ${result.health_fetched} 天`;
            }
            showProgress(msg + '。', '100%');
            document.getElementById('sync-password').value = '';
        } catch (err) {
            showProgress('同步失败：' + err.message, '0', true);
        } finally {
            btn.disabled = false;
            btn.textContent = '同步数据';
        }
    };

    document.getElementById('backfill-btn').onclick = async () => runSyncAction(
        'backfill-btn',
        '补采中...',
        '补采活动详情',
        '正在补采活动详情数据...',
        () => API.backfillDetails(100),
        r => `补采完成，成功获取 ${r.filled} 条详情，共检查 ${r.total} 条。`
    );

    document.getElementById('health-sync-btn').onclick = async () => runSyncAction(
        'health-sync-btn',
        '同步中...',
        '同步健康数据',
        '正在获取健康数据...',
        () => API.healthSync(14),
        r => `健康数据同步完成，获取 ${r.fetched} 天数据。`
    );

    document.getElementById('weather-backfill-btn').onclick = async () => runSyncAction(
        'weather-backfill-btn',
        '补采中...',
        '补采天气数据',
        '正在补采天气数据...',
        () => API.backfillWeather(100),
        r => `天气数据补采完成，成功获取 ${r.filled} 条，共检查 ${r.total} 条。`
    );
});

function showProgress(text, width, isError = false) {
    const progressDiv = document.getElementById('sync-progress');
    const fill = document.getElementById('sync-progress-fill');
    const statusText = document.getElementById('sync-status-text');
    progressDiv.style.display = 'block';
    fill.style.width = width;
    statusText.textContent = text;
    statusText.className = isError ? 'small error-text' : 'muted small';
}

async function runSyncAction(id, busyText, idleText, startText, action, successText) {
    const btn = document.getElementById(id);
    btn.disabled = true;
    btn.textContent = busyText;
    showProgress(startText, '18%');
    try {
        const result = await action();
        showProgress(successText(result), '100%');
    } catch (err) {
        showProgress('操作失败：' + err.message, '0', true);
    } finally {
        btn.disabled = false;
        btn.textContent = idleText;
    }
}
