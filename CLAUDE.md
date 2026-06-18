# CLAUDE.md (Group 6 project context)

Orientation for any Claude Code session working in this repo. Read this first.

## Team rules for AI / Claude sessions (no exceptions)

These are hard team rules. They apply to every team member and every AI session, and they
override any default behavior.

1. **Never add a `Co-Authored-By` trailer, or any Claude, AI, or agent attribution of any
   kind, to git commit messages.** Write plain commit messages with no co-author line.
2. **Writing style for any AI generated text** (commit messages, README, docs, comments, code):
   - Do not use em dashes (the long dash). Use a period, a comma, or parentheses instead.
   - Do not use semicolons. Use two sentences or a comma.
   - Avoid joined "word1-word2" words in prose. They should be very rare. (Hyphens inside real
     identifiers like file names or package names such as `ibm-db` are fine.)

## Current tasks

See TASKS.md for the live task board (who owns what, priorities, and the recommended order).
The project is far along. The remaining work is requirement coverage, code clarity, and exam
prep, not new features. When you finish a task, tick its checkbox in TASKS.md, then commit and
push so the rest of the team stays in sync.

## What this is

A take home analytics assignment (brief in guidelines.md): an interactive Streamlit dashboard
on airline operations, sourced from a DB2 database, prepared with Polars. Our concept is route
revenue and network performance for schema ATTGRP6.

## Key files

- `app.py`: the Streamlit dashboard (4 tabs: Route Performance, Time and Cabin, Fleet, Data).
- `prepare_data.py`: reads and aggregates DB2 with SQL, joins and builds features in Polars,
  writes the `data/*.parquet` files the app reads. Run this to refresh data.
- `db.py`: DB2 connection config (ATTGRP6), engine, helpers.
- `data/*.parquet`: prepared outputs ready for the dashboard. The app runs only from these.
- `README.md`: submission README (scope, business questions, findings, setup, limitations).
- `project_plan.md`: dashboard concept and design decisions.
- `guidelines.md`: the assignment rubric we are graded against.

## Run it

```zsh
# one time: install uv if missing
curl -LsSf https://astral.sh/uv/install.sh | sh

# env and deps
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt

# (optional) refresh prepared data from DB2 (needs DB access, see below)
python prepare_data.py --check
python prepare_data.py

# run the dashboard (works offline from the committed Parquet files)
streamlit run app.py
```

## Gotchas

- **DB access:** `prepare_data.py` needs the DB2 server (`52.211.123.34:25010`, schema
  ATTGRP6) reachable plus credentials. Defaults live in `db.py`. Override with a `.env`
  (`DB_USERNAME`, `DB_PASSWORD`, and so on). `.env` is git ignored. The dashboard does not need
  the DB. It reads the committed Parquet files.
- **`ibm-db`** compiles a native driver on install. It needs Xcode CLT on macOS.
- **Never commit** the virtual environment (`att-env/` or `.venv/`). It is already git ignored.
- Regenerate `requirements.txt` after dependency changes with the same uv export command that
  created it (recorded in the file header).
