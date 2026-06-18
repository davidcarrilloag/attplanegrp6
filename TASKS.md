# Group 6 — Task Board

Shared task division for the ATTGRP6 airline dashboard submission. Derived from a full
audit against `guidelines.md`. **Project is ~85% complete** — all 7 minimum technical
requirements pass; remaining work is submission packaging + presentation prep, not engineering.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## 🔴 Blockers — must be done to submit

- [x] **(Lasca)** Add "Group Members" section to `README.md`
- [x] **(Lasca)** Generate runtime `requirements.txt` from the lockfile
- [ ] **(David)** Build final `group_6_plane_dashboard.zip` — top-level folder
  `group_6_plane_dashboard/` containing `app.py`, `db.py`, `prepare_data.py`,
  `requirements.txt`, `README.md`, `pyproject.toml`, `uv.lock`, `s04_group_project.ipynb`,
  `data/*.parquet`. **Exclude** `att-env/`, `.git`, `.DS_Store`. **Do this LAST** so it
  captures the finalized files.

## 🟠 High — where the grade is won (Insight 25% + Communication 5%)

- [ ] **(Nico)** Write `DEMO_SCRIPT.md` — ~10-min live-demo runsheet: 1 min business framing,
  2 min DB2→Polars→Parquet prep rationale (why SQL-aggregate the 248.6M-row TICKETS table),
  5 min tab walkthrough (NAP–LAS revenue → efficiency scatter → monthly cabin → CRJ-900 fleet),
  2 min limitations + next steps.
- [ ] **(David)** Write `QUESTIONS_AND_ANSWERS.md` — anticipate grader Qs: why these metrics;
  why each join (TICKETS→ROUTES, ROUTES→AIRPORTS, FLIGHTS→AIRPLANES) and why LEFT joins;
  monthly vs daily aggregation; assumptions (taxes COALESCE→0, scheduled vs completed flights,
  flight_minutes as duration proxy); improvement roadmap.

## 🟡 Medium — correctness + polish

- [ ] **(Nico)** Guard zero/null division in efficiency metrics so `revenue_per_distance` /
  `revenue_per_flight_minute` never produce inf/NaN — `prepare_data.py` (~L172-176, L210-214)
  and `app.py` (~L162-165). Re-run `prepare_data.py` and confirm charts are clean.
- [ ] **(Nico)** Add an in-dashboard "Key Findings" section/tab in `app.py` so the app stands
  alone without the README.
- [ ] **(Nico)** Add a caption on the Fleet tab noting it is independent of the commercial
  sidebar filters (or wire the filter through) — avoids a "why didn't it update?" misread.

## 🟢 Low — optional upside (only after blockers + demo prep)

- [ ] **(Nico)** Add `st.download_button` CSV export to the three preview tables.
- [ ] **(Nico)** Add a "Route Map" tab (`plotly` `scatter_geo`) using the lat/long already in
  `route_monthly_revenue.parquet` — the one missing analytical angle.
- [ ] **(David)** Remove or document the stray `data/main_clean.parquet`; confirm `att-env/`
  stays out of git and the ZIP.

---

## Recommended sequence

1. **Lasca:** README members + `requirements.txt` ✅ (done — unblocks the ZIP)
2. **Nico (parallel):** zero/null division guard → re-run `prepare_data.py`, verify charts
3. **Nico:** in-app Key Findings + fleet caption (+ CSV downloads if time)
4. **Nico + David (parallel):** `DEMO_SCRIPT.md` / `QUESTIONS_AND_ANSWERS.md`
5. **David:** cleanup stray parquet, confirm `att-env` excluded
6. **Lasca:** verify all blockers closed, app runs clean → green-light packaging
7. **David:** build `group_6_plane_dashboard.zip` (final step)
8. *(Optional)* Nico adds Route Map → re-zip
9. **All:** one full 10-min demo dry-run before submission

## Key risks

- **Package before fixes land** → stale submission. ZIP is gated as the last step.
- **Division-by-zero defect** could surface as inf/NaN mid-demo. Fix scheduled early (step 2).
- **Q&A on join correctness / double-counting** — be ready to explain it (Q&A doc).
- **DB2 reproducibility** — a grader won't have DB credentials/VPN. README must state the app
  runs **from the prepared Parquet files, no live DB needed**.
