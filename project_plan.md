# Project Plan

## Dashboard Concept

Build a Streamlit dashboard for airline management focused on **route revenue and network performance** for schema `ATTGRP6`.

The dashboard should help stakeholders identify which routes, cabins, periods, and aircraft create the strongest commercial performance, and where operational review may be useful.

## Audience

- Airline management
- Route planning team
- Commercial analytics team
- Fleet operations team

## Core Business Questions

1. Which routes generate the most revenue, ticket volume, and average ticket value?
2. Which routes are most efficient in revenue per kilometer and revenue per flight minute?
3. How does revenue change over time by cabin class?
4. Which aircraft or aircraft models are most heavily used across scheduled flights?

The first three questions satisfy the minimum requirement. The fourth adds an operational section and connects the commercial dashboard to fleet usage.

## Source Tables

- `ATTGRP6.TICKETS`
- `ATTGRP6.ROUTES`
- `ATTGRP6.AIRPORTS`
- `ATTGRP6.FLIGHTS`
- `ATTGRP6.AIRPLANES`

`PASSENGERS` is optional and should only be used in aggregated form if time allows.

## Required Joins

- `TICKETS` to `ROUTES` on `ROUTE_CODE`
- `ROUTES` to `AIRPORTS` for origin and destination airport metadata
- `FLIGHTS` to `ROUTES` on `ROUTE_CODE`
- `FLIGHTS` to `AIRPLANES` on aircraft registration

## Prepared Data Outputs

Because `ATTGRP6.TICKETS` has more than 248 million rows, the app should not load raw tickets. Prepare small Parquet outputs instead:

- `data/route_revenue.parquet`
- `data/monthly_revenue.parquet`
- `data/cabin_revenue.parquet`
- `data/fleet_utilization.parquet`

## Dashboard Sections

1. KPI overview: total revenue, tickets sold, average ticket value, routes, aircraft.
2. Route performance: top routes by revenue and ticket volume.
3. Route efficiency: revenue per distance and per flight minute.
4. Time and cabin performance: monthly revenue and cabin contribution.
5. Fleet utilization: flights and distance by aircraft model or registration.

## Minimum Filters

- Date or month range
- Cabin class
- Origin airport or country
- Destination airport or country
- Aircraft model for fleet section

## Key Implementation Principle

Use SQL only to reduce very large DB2 tables to manageable extracts or aggregates. Use Polars for the final cleaning, joins, feature engineering, and dashboard-ready summaries.
