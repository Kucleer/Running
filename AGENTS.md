# AGENTS.md - Garmin AI Coach

## Project Status
This repository already contains a working implementation. Do not treat it as a pre-implementation scaffold.

Before changing behavior, inspect the existing code and tests. The original implementation plan is useful background, but the current source tree is the source of truth.

## Key Documents
- `README.md` - current product overview, setup notes, API list, and feature summary.
- `design.md` - original system design and architecture notes.
- `docs/superpowers/plans/2026-05-06-garmin-ai-coach-plan.md` - original phased implementation plan.
- `CHANGELOG.md` - recent project history, when present.

Some Chinese text may appear mojibake in PowerShell depending on console encoding. Prefer reading files with UTF-8 aware tooling when content matters.

## Architecture
- `backend/` - Python Flask backend.
  - `app.py` registers routes and serves the SPA. All API endpoints defined here. Report tasks tracked in module-level `report_tasks` dict (in-memory).
  - `database.py` owns SQLite initialization and `get_db()`. Auto-migrates existing databases with `IF NOT EXISTS` and `_migrate()`.
  - `config.py` reads/writes app config. `get_config(key)` returns value or hardcoded default.
  - `garmin_client.py` wraps `garminconnect`. Monkey-patches library for Garmin China (`garmin.cn`) - patches `DI_TOKEN_URL`, `IOS_SERVICE_URL`, and overrides `_establish_session`/login methods.
  - `sync_service.py` handles Garmin sync and persistence. For each new activity, also fetches detailed running dynamics.
  - `llm_client.py` wraps OpenAI-compatible LLM calls with exponential backoff retry (3 retries, jittered).
  - `report_generator.py` handles multi-agent report generation (4 agent roles: analyst, coach, strength, summarizer) and VDOT helpers.
  - `chat_service.py` handles chat sessions/history. `build_messages()` injects training summary + recent activities + health data + runner profile.
  - `splits.py` handles activity split parsing, normalization, and storage (supports multiple Garmin split formats).
- `frontend/` - pure HTML/CSS/JS SPA with hash routing (`#dashboard`, `#activities`, `#report`, `#chat`, `#settings`).
  - `js/api.js` - API client
  - `js/app.js` - route engine
  - `js/dashboard.js` - dashboard with VDOT, charts, health data
  - `js/activities.js` - activity list with filtering and detail view
  - `js/report.js` - training report generation and viewing
  - `js/chat.js` - AI chat with SSE streaming
  - `js/settings.js` - configuration and Garmin sync
- `tests/` - pytest suite (47 tests).
- `data/` - local SQLite database and Garmin token storage.

## Tech Stack
- Backend: Python 3 + Flask.
- Garmin: `garminconnect` 0.3+, using China-region Garmin Connect behavior.
- LLM: OpenAI SDK against OpenAI-compatible endpoints such as DeepSeek.
- Storage: SQLite, with WAL mode.
- Frontend: plain HTML/CSS/JS, Chart.js 4.4, marked.js from CDN.
- Packaging: PyInstaller.
- Runtime target: Windows, backend binds `127.0.0.1:5000` for normal local use.

## Runtime And Environment
- Database path comes from `RUNNING_DB_PATH`, defaulting to `data/running.db`.
- Garmin token storage defaults near the database under `data/garmin_tokens`.
- If the checked-in `venv/` points at a missing Python install, recreate it or use a fresh virtual environment in the workspace.
- The app should be launched from the repository root.

## Commands
- Install dependencies: `pip install -r requirements.txt`
- Run all tests: `pytest tests/ -v`
- Run a single test file: `pytest tests/test_database.py -v`
- Run a single test: `pytest tests/test_api.py::test_stats_endpoint -v`
- Start app: `python -c "from backend.app import create_app; create_app().run(host='127.0.0.1', port=5000, threaded=True)"`
- Windows launcher: `run.bat`

## Development Rules
- Use `backend.database.get_db()` for DB access and close connections after use.
- Keep SQLite migrations/idempotent initialization compatible with existing local data.
- Preserve WAL journal mode.
- Do not store Garmin passwords; token/session persistence belongs in local token storage only.
- Garmin login may require captcha or saved-token fallback; API responses should surface `need_captcha` where relevant.
- LLM multi-agent report rounds are controlled by `report_rounds`, default `4`.
- Frontend routes use hash routing: `#dashboard`, `#activities`, `#report`, `#chat`, `#settings`.
- Keep changes scoped. There are already implementation files and tests; avoid rewriting from the old plan unless explicitly requested.
- Report generation runs in background `threading.Thread`. Progress tracked via in-memory `report_tasks` dict (resets on server restart).
- Chat SSE streaming: `/api/chat/ask` returns `text/event-stream` with JSON chunks `{chunk: ...}` and `[DONE]` terminator.
- LLM API key masking: `/api/config` GET masks key as `XXXX****XXXX`; POST skips update if value contains `****`.
- Health data sync is separate from activity sync (`/api/health/sync`).

## Testing
Tests use `conftest.py` fixtures:
- `test_db_path` creates a temp file (cleaned up after test)
- `app` sets `RUNNING_DB_PATH` to it and calls `create_app()`
- `client` provides Flask test client
Each test gets a fresh empty database.

## Git Notes
- The worktree may contain user changes. Do not revert unrelated modifications.
- Commit message style follows conventional prefixes, commonly `feat: ...`, `fix: ...`, and `test: ...`.
