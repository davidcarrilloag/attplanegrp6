from __future__ import annotations

from pathlib import Path

import polars as pl

from db import DBConfig, make_engine, read_sql, table_name, table_row_counts


DATA_DIR = Path("data")


def normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.strip().lower() for name in df.columns})


def read_reference_tables(config: DBConfig) -> dict[str, pl.DataFrame]:
    engine = make_engine(config)
    routes = normalize_columns(
        read_sql(
            engine,
            f"""
            SELECT
                ROUTE_CODE,
                ORIGIN,
                DESTINATION,
                PARENT_ROUTE,
                LEG_NUMBER,
                DISTANCE,
                FLIGHT_MINUTES
            FROM {table_name("ROUTES", config)}
            """,
        )
    )
    airports = normalize_columns(
        read_sql(
            engine,
            f"""
            SELECT
                IATA_CODE,
                AIRPORT,
                CITY,
                COUNTRY,
                CONTINENT,
                LATITUDE,
                LONGITUDE,
                AIRPORT_TAX
            FROM {table_name("AIRPORTS", config)}
            """,
        )
    )
    airplanes = normalize_columns(
        read_sql(
            engine,
            f"""
            SELECT
                AIRCRAFT_REGISTRATION,
                MODEL,
                COALESCE(SEATS_BUSINESS, 0) AS SEATS_BUSINESS,
                COALESCE(SEATS_PREMIUM, 0) AS SEATS_PREMIUM,
                COALESCE(SEATS_ECONOMY, 0) AS SEATS_ECONOMY,
                CREW_MEMBERS,
                BUILD_DATE,
                FUEL_GALLONS_HOUR,
                MAINTENANCE_TAKEOFFS,
                MAINTENANCE_FLIGHT_HOURS,
                TOTAL_FLIGHT_DISTANCE
            FROM {table_name("AIRPLANES", config)}
            """,
        )
    ).with_columns(
        (
            pl.col("seats_business")
            + pl.col("seats_premium")
            + pl.col("seats_economy")
        ).alias("seat_capacity")
    )
    return {"routes": routes, "airports": airports, "airplanes": airplanes}


def read_ticket_monthly_aggregate(config: DBConfig) -> pl.DataFrame:
    engine = make_engine(config)
    return normalize_columns(
        read_sql(
            engine,
            f"""
            SELECT
                ROUTE_CODE,
                CLASS AS CABIN_CLASS,
                YEAR(DEPARTURE) AS DEPARTURE_YEAR,
                MONTH(DEPARTURE) AS DEPARTURE_MONTH,
                COUNT(*) AS TICKETS_SOLD,
                SUM(TOTAL_AMOUNT) AS TOTAL_REVENUE,
                AVG(TOTAL_AMOUNT) AS AVG_TICKET_VALUE,
                SUM(PRICE) AS FARE_REVENUE,
                SUM(COALESCE(AIRPORT_TAX, 0) + COALESCE(LOCAL_TAX, 0)) AS TAX_REVENUE
            FROM {table_name("TICKETS", config)}
            GROUP BY
                ROUTE_CODE,
                CLASS,
                YEAR(DEPARTURE),
                MONTH(DEPARTURE)
            """,
        )
    )


def read_flight_route_aggregate(config: DBConfig) -> pl.DataFrame:
    engine = make_engine(config)
    return normalize_columns(
        read_sql(
            engine,
            f"""
            SELECT
                AIRPLANE AS AIRCRAFT_REGISTRATION,
                ROUTE_CODE,
                COUNT(*) AS SCHEDULED_FLIGHTS,
                MIN(DEPARTURE) AS FIRST_DEPARTURE,
                MAX(DEPARTURE) AS LAST_DEPARTURE
            FROM {table_name("FLIGHTS", config)}
            GROUP BY
                AIRPLANE,
                ROUTE_CODE
            """,
        )
    )


def enrich_route_metrics(
    ticket_monthly: pl.DataFrame,
    routes: pl.DataFrame,
    airports: pl.DataFrame,
) -> pl.DataFrame:
    origin_airports = airports.rename(
        {
            "iata_code": "origin",
            "airport": "origin_airport",
            "city": "origin_city",
            "country": "origin_country",
            "continent": "origin_continent",
            "latitude": "origin_latitude",
            "longitude": "origin_longitude",
            "airport_tax": "origin_airport_tax",
        }
    )
    destination_airports = airports.rename(
        {
            "iata_code": "destination",
            "airport": "destination_airport",
            "city": "destination_city",
            "country": "destination_country",
            "continent": "destination_continent",
            "latitude": "destination_latitude",
            "longitude": "destination_longitude",
            "airport_tax": "destination_airport_tax",
        }
    )
    return (
        ticket_monthly.lazy()
        .join(routes.lazy(), on="route_code", how="left")
        .join(origin_airports.lazy(), on="origin", how="left")
        .join(destination_airports.lazy(), on="destination", how="left")
        .with_columns(
            pl.date(
                pl.col("departure_year"),
                pl.col("departure_month"),
                1,
            ).alias("departure_month_date"),
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias(
                "computed_avg_ticket_value"
            ),
            (pl.col("total_revenue") / pl.col("distance")).alias(
                "revenue_per_distance"
            ),
            (pl.col("total_revenue") / pl.col("flight_minutes")).alias(
                "revenue_per_flight_minute"
            ),
        )
        .collect()
    )


def build_route_revenue(route_monthly: pl.DataFrame) -> pl.DataFrame:
    group_cols = [
        "route_code",
        "origin",
        "destination",
        "origin_city",
        "origin_country",
        "origin_continent",
        "destination_city",
        "destination_country",
        "destination_continent",
        "distance",
        "flight_minutes",
    ]
    return (
        route_monthly.lazy()
        .group_by(group_cols)
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("fare_revenue").sum().alias("fare_revenue"),
            pl.col("tax_revenue").sum().alias("tax_revenue"),
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias(
                "avg_ticket_value"
            ),
            (pl.col("total_revenue") / pl.col("distance")).alias(
                "revenue_per_distance"
            ),
            (pl.col("total_revenue") / pl.col("flight_minutes")).alias(
                "revenue_per_flight_minute"
            ),
        )
        .sort("total_revenue", descending=True)
        .collect()
    )


def build_monthly_revenue(route_monthly: pl.DataFrame) -> pl.DataFrame:
    return (
        route_monthly.lazy()
        .group_by("departure_month_date", "departure_year", "departure_month", "cabin_class")
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("fare_revenue").sum().alias("fare_revenue"),
            pl.col("tax_revenue").sum().alias("tax_revenue"),
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias(
                "avg_ticket_value"
            )
        )
        .sort("departure_month_date", "cabin_class")
        .collect()
    )


def build_cabin_revenue(route_monthly: pl.DataFrame) -> pl.DataFrame:
    return (
        route_monthly.lazy()
        .group_by("cabin_class")
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("fare_revenue").sum().alias("fare_revenue"),
            pl.col("tax_revenue").sum().alias("tax_revenue"),
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias(
                "avg_ticket_value"
            )
        )
        .sort("total_revenue", descending=True)
        .collect()
    )


def build_fleet_utilization(
    flight_routes: pl.DataFrame,
    routes: pl.DataFrame,
    airplanes: pl.DataFrame,
) -> pl.DataFrame:
    return (
        flight_routes.lazy()
        .join(routes.lazy(), on="route_code", how="left")
        .join(airplanes.lazy(), on="aircraft_registration", how="left")
        .with_columns(
            (pl.col("scheduled_flights") * pl.col("distance")).alias(
                "scheduled_distance"
            ),
            (
                pl.col("scheduled_flights")
                * pl.col("flight_minutes")
                / 60
            ).alias("scheduled_flight_hours"),
            (
                pl.col("scheduled_flights")
                * pl.col("flight_minutes")
                / 60
                * pl.col("fuel_gallons_hour")
            ).alias("estimated_fuel_gallons"),
        )
        .group_by(
            "aircraft_registration",
            "model",
            "seat_capacity",
            "maintenance_takeoffs",
            "maintenance_flight_hours",
            "total_flight_distance",
        )
        .agg(
            pl.col("scheduled_flights").sum().alias("scheduled_flights"),
            pl.col("scheduled_distance").sum().alias("scheduled_distance"),
            pl.col("scheduled_flight_hours").sum().alias("scheduled_flight_hours"),
            pl.col("estimated_fuel_gallons").sum().alias("estimated_fuel_gallons"),
            pl.col("route_code").n_unique().alias("routes_served"),
        )
        .sort("scheduled_flights", descending=True)
        .collect()
    )


def build_route_capacity(
    flight_routes: pl.DataFrame,
    route_revenue: pl.DataFrame,
    airplanes: pl.DataFrame,
) -> pl.DataFrame:
    """Route-level load factor = tickets sold / available seats.

    Available seats per route are the scheduled flights times the seat capacity of
    the aircraft that flew them, summed across every aircraft on the route. We join
    that to the route revenue table so the result keeps the geographic attributes
    (continent/country) used by the dashboard filters.
    """
    seats_per_route = (
        flight_routes.lazy()
        .join(
            airplanes.lazy().select("aircraft_registration", "seat_capacity"),
            on="aircraft_registration",
            how="left",
        )
        .with_columns(
            (pl.col("scheduled_flights") * pl.col("seat_capacity")).alias("aircraft_seats")
        )
        .group_by("route_code")
        .agg(
            pl.col("scheduled_flights").sum().alias("scheduled_flights"),
            pl.col("aircraft_seats").sum().alias("available_seats"),
            pl.col("aircraft_registration").n_unique().alias("aircraft_used"),
        )
    )
    return (
        route_revenue.lazy()
        .join(seats_per_route, on="route_code", how="inner")
        .with_columns(
            pl.when(pl.col("available_seats") > 0)
            .then(pl.col("tickets_sold") / pl.col("available_seats"))
            .otherwise(None)
            .alias("load_factor")
        )
        .filter(pl.col("load_factor").is_not_null())
        .sort("load_factor", descending=True)
        .collect()
    )


def prepare_all(config: DBConfig | None = None, output_dir: Path = DATA_DIR) -> None:
    config = config or DBConfig.from_env()
    output_dir.mkdir(exist_ok=True)

    refs = read_reference_tables(config)
    ticket_monthly = read_ticket_monthly_aggregate(config)
    route_monthly = enrich_route_metrics(
        ticket_monthly,
        refs["routes"],
        refs["airports"],
    )
    flight_routes = read_flight_route_aggregate(config)
    route_revenue = build_route_revenue(route_monthly)

    outputs = {
        "route_monthly_revenue.parquet": route_monthly,
        "route_revenue.parquet": route_revenue,
        "monthly_revenue.parquet": build_monthly_revenue(route_monthly),
        "cabin_revenue.parquet": build_cabin_revenue(route_monthly),
        "fleet_utilization.parquet": build_fleet_utilization(
            flight_routes,
            refs["routes"],
            refs["airplanes"],
        ),
        "route_capacity.parquet": build_route_capacity(
            flight_routes,
            route_revenue,
            refs["airplanes"],
        ),
    }
    for filename, df in outputs.items():
        df.write_parquet(output_dir / filename)
        print(f"Wrote {output_dir / filename}: {df.height:,} rows x {df.width:,} columns")


def check_connection(config: DBConfig | None = None) -> None:
    config = config or DBConfig.from_env()
    engine = make_engine(config)
    counts = table_row_counts(engine, config)
    print(f"Connected to {config.database} as {config.username}; schema={config.schema}")
    print(counts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare ATTGRP6 dashboard datasets.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify DB connection and list schema table counts.",
    )
    args = parser.parse_args()

    cfg = DBConfig.from_env()
    if args.check:
        check_connection(cfg)
    else:
        prepare_all(cfg)
