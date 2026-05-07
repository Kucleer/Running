# AGENTS.md — Garmin AI Coach

## Repo status
No code exists yet. This is a **pre-implementation** repo with design and implementation plan only. Do not search for source files — follow the plan.

## Key documents (read first)
- `design.md` — full system design: architecture, tech stack, API design, data model, multi-agent flow
- `docs/superpowers/plans/2026-05-06-garmin-ai-coach-plan.md` — phased implementation plan with exact file paths, test code, and steps

## Implementation rules
- The plan file is the **source of truth** for what to build and in what order
- Follow test-first approach: write the test, confirm it fails, then implement
- Directory layout as defined in the plan:
  - `backend/` — Python Flask modules (`app.py`, `database.py`, `garmin_client.py`, `llm_client.py`, `report_generator.py`, `chat_service.py`, `sync_service.py`, `config.py`)
  - `frontend/` — HTML/CSS/JS SPA (`index.html`, `css/style.css`, `js/*.js`)
  - `tests/` — pytest files (`conftest.py`, `test_database.py`, etc.)
- Database path: `RUNNING_DB_PATH` env var, defaults to `data/running.db`
- Database uses WAL journal mode; all tables use `IF NOT EXISTS`
- `conftest.py` provides `test_db_path`, `app`, and `client` fixtures

## Tech stack (verified from design/plan)
- **Backend**: Python 3 + Flask, `garminconnect` (China region, `domain='cn'`), OpenAI SDK (DeepSeek-compatible), cryptography
- **Frontend**: pure HTML/CSS/JS SPA, Chart.js 4.4, marked.js (CDN)
- **Storage**: SQLite (tables: `activities`, `chat_history`, `config`)
- **Packaging**: PyInstaller
- **Platform**: Windows, backend binds `127.0.0.1:5000`

## Commands
- Run all tests: `pytest tests/ -v`
- Run a single test file: `pytest tests/test_database.py -v`
- Run a single test: `pytest tests/test_api.py::test_stats_endpoint -v`
- Install deps: `pip install -r requirements.txt`

## Conventions
- Commit messages are Chinese-prefixed: `feat: ...` (observed in plan)
- Use `backend.database.get_db()` for all DB access; close after use
- Garmin needs captcha handling — login may return `{need_captcha: true}`
- LLM multi-agent rounds configurable via `report_rounds` config key (default 4)
- Frontend uses hash routing (`#dashboard`, `#activities`, `#report`, `#chat`, `#settings`)
