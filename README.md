# Running AI Coach 🏃

本地化佳明运动数据分析与 AI 教练系统。自动同步[佳明中国区](https://connect.garmin.cn)运动数据，基于可配置的大语言模型（DeepSeek 等）通过**多智能体头脑风暴**生成专业训练报告，并支持基于历史数据的智能问答。所有数据、配置和对话记录完全本地化存储，保障隐私。

## 功能

#### 仪表盘
- 跑量 / 配速趋势统计（支持自定义时间范围和快捷筛选：近一周 / 一月 / 三月 / 半年 / 一年）
- **VDOT 跑力**：基于最佳 5K+ 成绩的 Jack Daniels 公式计算，含各距离预测成绩、训练配速区间（E/M/T/I/R）、心率区间（Karvonen 储备心率法）
- 健康数据：HRV、睡眠分数、静息心率、身体电量、平均压力双轴趋势图

#### 运动记录
- 列表筛选（类型 / 日期 / 关键词）
- 活动详情：基础指标 + 跑步动态（步频、触地时间、垂直振幅、步幅、训练效果、VO2max、乳酸阈值）

#### AI 训练报告
- 多智能体头脑风暴：数据分析师 → 跑步教练 → 力量专家 → 主教练（轮数可配，默认 4 轮）
- 报告含：训练数据统计、跑步能力趋势、训练建议、成绩预测
- 历史报告持久化保存，支持查看和删除

#### AI 问答
- 多会话隔离，每个会话独立上下文
- 基于真实训练数据和跑者基础信息回答
- 支持连续多轮对话

#### 佳明数据同步
- 自动 Token 持久化，免重复登录（避免 429 限流）
- 活动列表同步 + 详情补采（步频、触地时间等跑步动态）
- 健康数据同步（HRV、睡眠、身体电量、压力、静息心率）

#### 设置
- LLM 配置（API 地址 / Key / 模型 / 报告轮数）
- 跑者基础信息（年龄、性别、身高、体重、静息心率、最大心率、跑步目标）
- 佳明账户管理、数据同步、健康数据同步、活动详情补采

---

## 快速开始

### 前置要求
- Python 3.12+
- 佳明中国区账户

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动应用
双击 `run.bat`，或执行：
```bash
python -c "from backend.app import create_app; create_app().run(host='127.0.0.1', port=5000, threaded=True)"
```

### 3. 初始化
1. 浏览器打开 `http://127.0.0.1:5000`
2. 进入 **设置** 页面，输入佳明账户邮箱和密码，点击「同步数据」
3. 进入 **设置** → **LLM 配置**，填入 API 地址和 Key，保存
4. （可选）设置 **跑者基础信息** 以获得更精准的心率区间和 VDOT 分析
5. （可选）点击「补采活动详情」获取步频/触地时间等跑步动态数据
6. （可选）点击「同步健康数据」获取 HRV/睡眠等

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3 + Flask |
| 数据库 | SQLite（WAL 模式） |
| 佳明 API | [garminconnect](https://github.com/cyberjunky/python-garminconnect) 0.3+ |
| LLM | OpenAI SDK（兼容 DeepSeek 等） |
| 前端 | 纯 HTML/CSS/JS SPA，hash 路由 |
| 图表 | Chart.js 4.4 |
| Markdown | marked.js |
| 测试 | pytest |
| 打包 | PyInstaller |

---

## 项目结构

```
running/
├── backend/
│   ├── app.py              # Flask 主应用，API 路由
│   ├── database.py         # 数据库初始化、连接、迁移
│   ├── garmin_client.py    # 佳明 API 封装（登录、同步、健康数据）
│   ├── sync_service.py     # 数据同步服务
│   ├── report_generator.py # 多智能体报告引擎 + VDOT 计算
│   ├── chat_service.py     # 对话管理（会话、消息）
│   ├── llm_client.py       # LLM API 调用（重试+退避）
│   └── config.py           # 配置读写
├── frontend/
│   ├── index.html          # SPA 壳
│   ├── css/style.css       # 全局样式（CSS 变量主题）
│   └── js/
│       ├── api.js          # API 客户端
│       ├── app.js          # 路由引擎
│       ├── dashboard.js    # 仪表盘
│       ├── activities.js   # 运动记录
│       ├── report.js       # 训练报告
│       ├── chat.js         # AI 问答
│       └── settings.js     # 设置
├── tests/                  # pytest 测试（47 个）
├── data/                   # 数据库文件（自动创建）
├── run.bat                 # Windows 启动脚本
└── requirements.txt
```

---

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RUNNING_DB_PATH` | `data/running.db`（项目目录下） | 数据库路径 |
| `GARMIN_TOKENSTORE` | `data/garmin_tokens` | 佳明 Token 持久化路径 |

### 页面配置（存入数据库 `config` 表）

| 键 | 默认值 | 说明 |
|------|--------|------|
| `llm_base_url` | `https://api.deepseek.com/v1` | LLM API 地址 |
| `llm_api_key` | （空） | LLM API Key |
| `llm_model` | `deepseek-chat` | 模型名称 |
| `report_rounds` | `4` | 报告生成轮数（3-5） |
| `profile_age` ~ `profile_race_goal` | （空） | 跑者基础信息 |

---

## API 端点（主要）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/stats` | 仪表盘统计数据（支持 `from`/`to` 日期筛选） |
| `GET` | `/api/vdot` | VDOT 跑力、成绩预测、配速/心率区间 |
| `GET` | `/api/health` | 健康数据（HRV/睡眠/压力/电量） |
| `POST` | `/api/health/sync` | 同步健康数据 |
| `GET` | `/api/activities` | 运动记录列表 |
| `GET` | `/api/activity/<id>` | 活动详情 |
| `POST` | `/api/sync` | 佳明数据同步 |
| `POST` | `/api/sync/backfill` | 活动详情补采 |
| `POST` | `/api/report/generate` | 生成训练报告 |
| `GET` | `/api/reports` | 历史报告列表 |
| `POST` | `/api/chat/ask` | AI 问答（SSE 流式） |
| `POST` | `/api/chat/sessions` | 创建对话会话 |
| `GET/POST` | `/api/config` | 配置读写 |

---

## 数据库表

| 表 | 说明 |
|------|------|
| `activities` | 活动记录（含基础指标和跑步动态） |
| `health_data` | 每日健康指标（HRV/睡眠/压力/电量） |
| `chat_sessions` | 对话会话 |
| `chat_history` | 对话消息记录 |
| `reports` | 历史训练报告 |
| `config` | 键值配置 |

---

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行单个文件
pytest tests/test_database.py -v

# 运行单个用例
pytest tests/test_api.py::test_stats_endpoint -v
```

---

## 常见问题

**同步失败 / 429 限流？**
系统使用 Token 持久化，首次同步后自动保存 Token，后续免登录。如仍遇到 429，等待几分钟后重试。

**VDOT 数据不显示？**
需要数据库中至少有 ≥5km 的跑步记录。VDOT 基于 Jack Daniels 公式从最佳 5K+ 成绩自动计算。

**跑步动态（步频/触地时间）缺失？**
进入设置页点击「补采活动详情」按钮，系统会逐条调用佳明 API 获取详细跑步动态数据。
