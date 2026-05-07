registerPage('#settings', async (container) => {
    container.innerHTML = `
        <h1 style="margin-bottom:16px">设置</h1>
        <div class="card">
            <h2>LLM 配置</h2>
            <div style="max-width:500px">
                <label>API 地址</label>
                <input id="cfg-base-url" type="text" placeholder="https://api.deepseek.com/v1">
                <label>API Key</label>
                <input id="cfg-api-key" type="password" placeholder="sk-...">
                <label>模型名称</label>
                <input id="cfg-model" type="text" placeholder="deepseek-chat">
                <label>报告生成轮数 (3-5)</label>
                <input id="cfg-rounds" type="number" min="3" max="5" value="4">
                <button class="btn" id="cfg-save-btn" style="margin-top:12px">保存配置</button>
                <p id="cfg-msg" style="margin-top:8px;font-size:13px"></p>
            </div>
        </div>
        <div class="card">
            <h2>跑者基础信息</h2>
            <div style="max-width:500px">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 12px">
                    <div><label>年龄</label><input id="profile-age" type="number" min="1" max="120" placeholder="28"></div>
                    <div><label>性别</label><select id="profile-gender"><option value="">请选择</option><option value="male">男</option><option value="female">女</option></select></div>
                    <div><label>身高 (cm)</label><input id="profile-height" type="number" min="50" max="250" placeholder="170"></div>
                    <div><label>体重 (kg)</label><input id="profile-weight" type="number" min="20" max="300" placeholder="65"></div>
                    <div><label>静息心率</label><input id="profile-resting-hr" type="number" min="30" max="120" placeholder="55"></div>
                    <div><label>最大心率</label><input id="profile-max-hr" type="number" min="80" max="250" placeholder="190"></div>
                </div>
                <label>跑步目标</label>
                <select id="profile-race-goal">
                    <option value="">请选择</option>
                    <option value="5k">5K</option>
                    <option value="10k">10K</option>
                    <option value="half_marathon">半马 (21.1K)</option>
                    <option value="marathon">全马 (42.2K)</option>
                </select>
                <button class="btn" id="profile-save-btn" style="margin-top:12px">保存信息</button>
                <p id="profile-msg" style="margin-top:8px;font-size:13px"></p>
            </div>
        </div>
        <div class="card">
            <h2>佳明账户</h2>
            <div style="max-width:500px">
                <label>邮箱</label>
                <input id="sync-email" type="email" placeholder="your@email.com">
                <label>密码</label>
                <input id="sync-password" type="password" placeholder="仅本地传输，不存储">
                <button class="btn" id="sync-btn" style="margin-top:12px">同步数据</button>
                <button class="btn btn-secondary" id="backfill-btn" style="margin-top:8px">补采活动详情</button>
                <button class="btn btn-secondary" id="health-sync-btn" style="margin-top:8px">同步健康数据 (HRV/睡眠)</button>
                <div id="sync-progress" style="margin-top:10px;display:none">
                    <div class="progress-bar"><div id="sync-progress-fill" class="fill" style="width:0"></div></div>
                    <p id="sync-status-text" style="font-size:13px;color:#888;margin-top:4px"></p>
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
            msg.style.color = 'green';
        } catch (err) {
            msg.textContent = '保存失败: ' + err.message;
            msg.style.color = 'red';
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
            msg.style.color = 'green';
        } catch (err) {
            msg.textContent = '保存失败: ' + err.message;
            msg.style.color = 'red';
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

        const progressDiv = document.getElementById('sync-progress');
        const fill = document.getElementById('sync-progress-fill');
        const statusText = document.getElementById('sync-status-text');
        progressDiv.style.display = 'block';
        fill.style.width = '30%';
        statusText.textContent = '正在连接佳明服务器...';

        try {
            const result = await API.sync(email, password);
            fill.style.width = '100%';
            statusText.textContent = `同步完成! 新增 ${result.new_count} 条记录，共检查 ${result.total_checked} 条`;
            document.getElementById('sync-password').value = '';
        } catch (err) {
            fill.style.width = '0';
            statusText.textContent = '同步失败: ' + err.message;
            statusText.style.color = 'red';
        } finally {
            btn.disabled = false;
            btn.textContent = '同步数据';
        }
    };

    document.getElementById('backfill-btn').onclick = async () => {
        const btn = document.getElementById('backfill-btn');
        const progressDiv = document.getElementById('sync-progress');
        const fill = document.getElementById('sync-progress-fill');
        const statusText = document.getElementById('sync-status-text');

        btn.disabled = true;
        btn.textContent = '补采中...';
        progressDiv.style.display = 'block';
        fill.style.width = '10%';
        statusText.textContent = '正在补采活动详情数据...';
        statusText.style.color = '';

        try {
            const result = await API.backfillDetails(100);
            fill.style.width = '100%';
            statusText.textContent = `补采完成! 成功获取 ${result.filled} 条详情，共检查 ${result.total} 条`;
        } catch (err) {
            fill.style.width = '0';
            statusText.textContent = '补采失败: ' + err.message;
            statusText.style.color = 'red';
        } finally {
            btn.disabled = false;
            btn.textContent = '补采活动详情 (步频/触地时间等)';
        }
    };

    document.getElementById('health-sync-btn').onclick = async () => {
        const btn = document.getElementById('health-sync-btn');
        const progressDiv = document.getElementById('sync-progress');
        const fill = document.getElementById('sync-progress-fill');
        const statusText = document.getElementById('sync-status-text');

        btn.disabled = true;
        btn.textContent = '同步中...';
        progressDiv.style.display = 'block';
        fill.style.width = '20%';
        statusText.textContent = '正在获取健康数据...';
        statusText.style.color = '';

        try {
            const result = await API.healthSync(14);
            fill.style.width = '100%';
            statusText.textContent = `健康数据同步完成! 获取 ${result.fetched} 天数据`;
        } catch (err) {
            fill.style.width = '0';
            statusText.textContent = '同步失败: ' + err.message;
            statusText.style.color = 'red';
        } finally {
            btn.disabled = false;
            btn.textContent = '同步健康数据 (HRV/睡眠)';
        }
    };
});
