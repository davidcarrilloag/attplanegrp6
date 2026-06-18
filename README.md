# ATT Plane Group 6

Streamlit dashboard for airline route revenue and network performance using the DB2 `ATTGRP6` schema.

## Group Members

- **Nicolas Wilches** — <nicolaswilches@icloud.com>
- **David Carrillo** — <davidcarrillo@student.ie.edu>
- **Lasca** — <mss@ab-on.com>
- **Nachi** — <nachi@student.ie.edu>
- **Siddharth** — <siddharth_murali@student.ie.edu>

## Project Scope

The dashboard is built for airline management, route planning, commercial analytics, and fleet operations teams. It focuses on revenue performance, route efficiency, monthly/cabin trends, and aircraft utilization.

## Business Questions

1. Which routes generate the most revenue, ticket volume, and average ticket value?
2. Which routes are most efficient in revenue per distance and revenue per flight minute?
3. How does revenue change over time by cabin class?
4. Which aircraft or aircraft models are most heavily used across scheduled flights?

## Data Source

- Database: `ATTPLANE`
- Schema: `ATTGRP6`
- Main tables: `TICKETS`, `ROUTES`, `AIRPORTS`, `FLIGHTS`, `AIRPLANES`
- `PASSENGERS` is not used in the current dashboard to avoid unnecessary personal data exposure.

Because `ATTGRP6.TICKETS` has about 248.6 million rows, the app does not query raw tickets directly. The preparation script aggregates DB2 data first, then uses Polars to join, enrich, and write dashboard-ready Parquet files.

## Prepared Outputs

Generated files:

- `data/route_monthly_revenue.parquet`
- `data/route_revenue.parquet`
- `data/monthly_revenue.parquet`
- `data/cabin_revenue.parquet`
- `data/fleet_utilization.parquet`

Current prepared totals:

- Revenue: about `$285B`
- Tickets sold: `248,622,081`
- Ticketed routes: `592`
- Aircraft used in scheduled flights: `272`

## Key Findings

- The highest-revenue route is `NAP` to `LAS`, generating about `$1.03B` from `610,931` tickets.
- The reverse route, `LAS` to `NAP`, is the second highest revenue route at about `$1.02B`.
- Economy is the largest cabin by total revenue, contributing about `$219.6B` from `170.5M` tickets.
- Premium has the highest average ticket value at about `$1,772`, despite much lower ticket volume than economy.
- `BOMBARDIER CRJ-900` is the most heavily scheduled aircraft model, with `539,304` scheduled flights across `41` aircraft.

## Setup

Clone the repository:

```zsh
git clone https://github.com/davidcarrilloag/attplanegrp6.git
cd attplanegrp6
```

Create and activate the virtual environment:

```zsh
uv venv --python 3.11
source .venv/bin/activate
```

Install dependencies:

```zsh
uv pip install -e ".[dev]"
```

If `uv` is not installed:

```zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Prepare Data

Check the DB2 connection:

```zsh
python prepare_data.py --check
```

Build the prepared Parquet files:

```zsh
python prepare_data.py
```

## Run the Dashboard

```zsh
streamlit run app.py
```

The app reads the prepared Parquet files from `data/`.

## Assumptions and Limitations

- Revenue analysis uses ticket `TOTAL_AMOUNT`, including fare and tax components.
- Route efficiency uses route distance and flight minutes from `ROUTES`.
- Fleet utilization uses scheduled flights, not completed or delayed operations.
- Passenger-level analysis is intentionally excluded from the dashboard.
- Prepared files should be regenerated if the DB2 source data changes.
