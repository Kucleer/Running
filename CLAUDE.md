# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A local, privacy-first Garmin data analysis and AI coach system for Chinese users. Backend Flask server syncs activity data from Garmin China, stores it in SQLite, and uses configurable LLM APIs to generate multi-agent training reports and power an interactive chat coach. Frontend is a single-page HTML/CSS/JS app.

## Commands

```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_database.py -v

# Run a single test
pytest tests/test_api.py::test_stats_endpoint -v

# Install dependencies
pip install -r requirements.txt

# Run the dev server (opens browser at http://127.0.0.1:5000)
python backend/app.py
```

## Architecture

**Backend** (`backend/`): Python 3 + Flask. All modules import from `backend.` prefix.

| File | Role |
|------|------|
| `app.py` | Flask routes, `create_app()` factory, main entry point. All API endpoints defined here. Report tasks tracked in module-level `report_tasks` dict (in-memory). |
| `database.py` | SQLite with WAL mode. `init_db()` creates tables with `IF NOT EXISTS` and runs automatic column migrations via `_migrate()`. `get_db()` opens a connection; callers must close it. |
| `config.py` | Key-value config store in `config` table. `get_config(key)` returns the value or a hardcoded default. `set_config()` upserts. |
| `garmin_client.py` | Wraps `garminconnect` library. **Monkey-patches the library's module-level globals** for Garmin China (`garmin.cn`) — patches `DI_TOKEN_URL`, `IOS_SERVICE_URL`, and overrides `_establish_session`/login methods on `Client`. Patches are applied/restored per login attempt. |
| `llm_client.py` | OpenAI SDK wrapper with exponential backoff retry (3 retries, jittered). Both `chat()` and `chat_stream()` generators. Retries on 429/5xx, timeouts, and connection errors. |
| `report_generator.py` | Multi-agent report engine. 4 agent roles (analyst, coach, strength, summarizer) do N rounds (configurable, default 4) of cross-talk via LLM. Includes Jack Daniels VDOT formula (`calc_vdot`), race time prediction, and training pace zone calculation. `generate_stream()` yields progress updates. |
| `chat_service.py` | Chat session management. Sessions stored in `chat_sessions` table, messages in `chat_history`. `build_messages()` injects training summary + recent activities + health data + runner profile into the system prompt. |
| `sync_service.py` | Orchestrates Garmin login then activity fetching. For each new activity, also fetches detailed running dynamics (cadence, ground contact time, etc.) and updates the row. |

**Frontend** (`frontend/`): SPA served by Flask as static files. Hash-based routing: `#dashboard`, `#activities`, `#report`, `#chat`, `#settings`. Uses Chart.js 4.4 and marked.js from CDN.

**Database** (SQLite at `data/running.db`, override with `RUNNING_DB_PATH` env var):

Tables: `activities` (Garmin activity data + running dynamics columns), `health_data` (HRV/sleep/stress daily), `chat_history` (per-session messages), `chat_sessions`, `config` (key-value), `reports` (generated report content).

The `activities` table has been extended with running dynamics columns (`avg_cadence`, `max_cadence`, `avg_ground_contact_time`, `avg_vertical_oscillation`, `avg_stride_length`, `training_effect`, `vo2max`, `lactate_threshold`, `detail_json`) — `init_db()` auto-migrates existing databases.

## Key Implementation Details

- **Garmin CN login**: Tries China region first, falls back to international. The `garminconnect` library doesn't natively support Garmin CN's OAuth flow, so `garmin_client.py` patches module-level `DI_TOKEN_URL` etc. and replaces `Client._establish_session` with a CN-specific version. Patches are restored on failure.
- **VDOT**: Jack Daniels formula with 1.065 correction factor. `calc_vdot()` computes from any run ≥5K distance. The `/api/vdot` endpoint finds the best-performance run and derives predictions + training pace zones.
- **Report generation**: Runs in a background `threading.Thread`. Progress tracked via in-memory `report_tasks` dict (resets on server restart). Reports are auto-saved to the `reports` table on completion.
- **Chat SSE streaming**: `/api/chat/ask` returns `text/event-stream`. The generator yields JSON chunks with `{chunk: ...}` and terminates with `[DONE]`.
- **Health data sync**: Separate from activity sync. `/api/health/sync` fetches HRV, sleep, body battery, stress, resting HR, VO2max for a configurable number of recent days.
- **Backfill**: `/api/sync/backfill` fills missing `detail_json` for existing activities without re-syncing everything.
- **LLM API key masking**: `/api/config` GET masks the key as `XXXX****XXXX` when returning to frontend. POST skips update if value contains `****`.

## Testing

Tests use `conftest.py` fixtures: `test_db_path` creates a temp file (cleaned up after test), `app` sets `RUNNING_DB_PATH` to it and calls `create_app()`, `client` provides Flask test client. Each test gets a fresh empty database.

## Packaging

PyInstaller spec at `pyinstaller.spec` bundles `backend/app.py` + `frontend/` into `RunningCoach.exe` (console mode). `run.bat` is the dev-start script — creates venv if needed, installs deps, launches server and opens browser.
