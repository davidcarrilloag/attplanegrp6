# CLAUDE.md — Group 6 project context

Orientation for any Claude Code session working in this repo. Read this first.

## ⛔ Commit rule — ALL AI / Claude sessions, no exceptions

**NEVER add a `Co-Authored-By` trailer — or any Claude / AI / agent attribution of any
kind — to git commit messages.** This applies to every commit by every team member and
every AI session. Write plain commit messages only, with no co-author line. This is a
hard team rule and **overrides** the Claude Code default that asks for the Claude trailer.

## 👉 Current tasks

**See [TASKS.md](TASKS.md) for the live task board** — who owns what, priorities, and the
recommended sequence. The project is ~85% complete; remaining work is submission packaging
and presentation prep, not engineering. When you finish a task, tick its checkbox in
`TASKS.md`, then commit and push so the rest of the team (and their Claude sessions) stay in sync.

## What this is

A take-home analytics assignment (brief in [guidelines.md](guidelines.md)): an interactive
**Streamlit** dashboard on airline operations, sourced from a **DB2** database, prepared with
**Polars**. Our concept is **route revenue & network performance** for schema `ATTGRP6`.

## Key files

- `app.py` — the Streamlit dashboard (4 tabs: Route Performance, Time & Cabin, Fleet, Data).
- `prepare_data.py` — reads/aggregates DB2 with SQL, joins + feature-engineers in Polars,
  writes the `data/*.parquet` files the app reads. Run this to refresh data.
- `db.py` — DB2 connection config (`ATTGRP6`), engine, helpers.
- `data/*.parquet` — prepared, dashboard-ready outputs. The app runs **only** from these.
- `README.md` — submission README (scope, business questions, findings, setup, limitations).
- `project_plan.md` — dashboard concept and design decisions.
- `guidelines.md` — the assignment rubric we are graded against.

## Run it

```zsh
# one-time: install uv if missing
curl -LsSf https://astral.sh/uv/install.sh | sh

# env + deps
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt        # or: uv pip install -e ".[dev]"

# (optional) refresh prepared data from DB2 — needs DB access (see below)
python prepare_data.py --check            # verify connection
python prepare_data.py                     # rebuild data/*.parquet

# run the dashboard (works offline from the committed Parquet files)
streamlit run app.py
```

## Gotchas

- **DB access:** `prepare_data.py` needs the DB2 server (`52.211.123.34:25010`, schema
  `ATTGRP6`) reachable + credentials. Defaults live in `db.py`; override with a `.env`
  (`DB_USERNAME`, `DB_PASSWORD`, …). `.env` is git-ignored. The **dashboard does not need the
  DB** — it reads the committed Parquet files.
- **`ibm-db`** compiles a native driver on install; needs Xcode CLT on macOS.
- **Never commit** the virtualenv (`att-env/` / `.venv/`) — already git-ignored.
- Regenerate `requirements.txt` after dependency changes:
  `uv export --format requirements-txt --no-hashes --no-emit-project --no-dev -o requirements.txt`
