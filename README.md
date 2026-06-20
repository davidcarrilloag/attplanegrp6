# ATT Plane Group 6

Streamlit dashboard for airline route revenue and network performance using the DB2 `ATTGRP6` schema.

## Group Members

- **Nicolás Alejandro Higuera Wilches**: <nicolaswilches@student.ie.edu>
- **David Carrillo Aguilera**: <davidcarrillo@student.ie.edu>
- **Martin Sebastian Schneider Vaquero**: <martin.schneider@student.ie.edu>
- **Ignacio Agustín Moreno**: <nachi@student.ie.edu>
- **Siddharth Murali**: <siddharth_murali@student.ie.edu>

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

- Cabin codes `B`, `E`, `P` do not follow intuitive names. We mapped them to fare tiers by
  their verified average fare (validated against the `FLIGHTS` prices Economy < Premium <
  Business): **B = Economy** (lowest fare), **E = Premium**, **P = Business** (highest fare).
- The top city pair by revenue is **GMP and LHR** at about `$4.17B`, counting both directions.
- The **Premium** cabin (code E) is the largest by revenue (about `$219.6B`) and by volume
  (about `170.5M` tickets). This is unusual and we treat it as a property of the dataset.
- The **Business** cabin (code P) has the highest average fare (about `$1,772`) but the lowest
  volume (about `6.7M` tickets).
- The **Economy** cabin (code B) is the cheapest at about `$749` average fare.
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

- **Cabin mapping:** ticket `CLASS` codes B/E/P do not match intuitive cabin names, so we
  mapped them to fare tiers by verified average fare (B = Economy, E = Premium, P = Business).
  The volumes do not follow a typical pattern (the Premium tier has the highest volume), which
  we treat as a property of the dataset, not a real commercial pattern.
- **Route grain:** route_code is directional, so the top routes view aggregates both directions
  into one city pair. The route table still shows directional detail.
- **Time coverage:** data runs 2010 to 2026, but 2026 is January only, so the date filter
  defaults to the last complete year to avoid skewing the monthly trend.
- Revenue uses ticket `TOTAL_AMOUNT` (fare plus tax). Yield is the average fare per distance or
  per flight minute, with guards against zero or null denominators.
- Fleet utilization uses scheduled flights, not completed or delayed operations.
- Passenger level analysis is intentionally excluded from the dashboard.
- Prepared files should be regenerated if the DB2 source data changes.
