from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="ATT Plane Analytics", layout="wide")

DATA_DIR = Path("data")
ROUTE_MONTHLY_PATH = DATA_DIR / "route_monthly_revenue.parquet"
FLEET_PATH = DATA_DIR / "fleet_utilization.parquet"

MONEY_COLUMNS = {
    "total_revenue",
    "fare_revenue",
    "tax_revenue",
    "avg_ticket_value",
    "computed_avg_ticket_value",
    "revenue_per_distance",
    "revenue_per_flight_minute",
}

# Cabin codes mapped to fare tiers by VERIFIED average fare, not by first letter.
# Live DB check: FLIGHTS prices are Economy < Premium < Business, and ticket fares rank
# B < E < P, so by fare B is the lowest tier and P the highest. See README for the note.
CABIN_LABELS = {
    "B": "Economy",
    "E": "Premium",
    "P": "Business",
}

# Electric blue theme: only the blue RGB channel (no red, no green), varied by intensity.
COLORWAY = [
    "#0000FF",
    "#000099",
    "#0000CC",
    "#000066",
    "#0000E6",
    "#0000B3",
    "#000080",
    "#00004D",
]

# Single source of truth for color: every color in the app is drawn from this scheme so
# the dashboard stays 100% coherent. It matches the dark theme in .streamlit/config.toml.
NAVY = "#06143A"      # gradient low, darkest
ELECTRIC = "#0000FF"  # gradient mid, primary accent (KPI cards, widgets)
CYAN = "#02CCFE"      # gradient high, highlight for the largest values and single data marks

# Value-sorted charts: larger = brighter, so the biggest values pop on the dark background.
BLUE_SCALE = [[0.0, NAVY], [0.5, ELECTRIC], [1.0, CYAN]]

px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = COLORWAY


def blue_palette(n):
    """n distinguishable blue tones, dark (low) to neon cyan (high), so the largest
    category is the brightest. Anchors: dark navy -> electric blue -> neon cyan."""
    anchors = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in (NAVY, ELECTRIC, CYAN)]
    if n <= 1:
        return [CYAN]

    def lerp(a, b, t):
        return tuple(round(a[c] + (b[c] - a[c]) * t) for c in range(3))

    tones = []
    for i in range(n):
        pos = i / (n - 1) * 2  # 0..2 across the two segments
        seg = min(int(pos), 1)
        rgb = lerp(anchors[seg], anchors[seg + 1], pos - seg)
        tones.append("#%02X%02X%02X" % rgb)
    return tones


def ranked_blue_map(df, category_col, value_col):
    """Map each category to a blue tone, the largest total getting electric blue."""
    order = (
        df.lazy()
        .group_by(category_col)
        .agg(pl.col(value_col).sum().alias("_value"))
        .sort("_value")
        .collect()
        .get_column(category_col)
        .to_list()
    )
    return {cat: tone for cat, tone in zip(order, blue_palette(len(order)))}


@st.cache_data
def load_parquet(path: Path) -> pl.DataFrame:
    df = pl.read_parquet(path)
    decimal_columns = [col for col in MONEY_COLUMNS if col in df.columns]
    if decimal_columns:
        df = df.with_columns(pl.col(decimal_columns).cast(pl.Float64))
    return df


def require_data_files() -> None:
    missing = [str(path) for path in [ROUTE_MONTHLY_PATH, FLEET_PATH] if not path.exists()]
    if missing:
        st.error("Prepared data files are missing.")
        st.code("\n".join(["python prepare_data.py", "", "Missing:"] + missing))
        st.stop()


def sorted_values(df: pl.DataFrame, column: str) -> list[str]:
    return (
        df.select(pl.col(column).drop_nulls().unique().sort())
        .to_series()
        .to_list()
    )


def with_all_option(values: list[str]) -> list[str]:
    return ["All"] + values


def select_all_filter(label: str, values: list[str]) -> str:
    return st.sidebar.selectbox(label, with_all_option(values))


def cabin_name_expr() -> pl.Expr:
    return (
        pl.when(pl.col("cabin_class") == "B")
        .then(pl.lit("Economy"))
        .when(pl.col("cabin_class") == "E")
        .then(pl.lit("Premium"))
        .when(pl.col("cabin_class") == "P")
        .then(pl.lit("Business"))
        .otherwise(pl.col("cabin_class"))
        .alias("cabin")
    )


def route_label_expr() -> pl.Expr:
    return (
        pl.col("origin")
        + " to "
        + pl.col("destination")
        + " ("
        + pl.col("route_code")
        + ")"
    ).alias("route_label")


def apply_commercial_filters(
    route_monthly_df: pl.DataFrame,
    origin_continent: str,
    destination_continent: str,
    origin_country: str,
    destination_country: str,
    cabin_classes: list[str],
    start_date: date,
    end_date: date,
) -> pl.DataFrame:
    lazy = route_monthly_df.lazy()
    if origin_continent != "All":
        lazy = lazy.filter(pl.col("origin_continent") == origin_continent)
    if destination_continent != "All":
        lazy = lazy.filter(pl.col("destination_continent") == destination_continent)
    if origin_country != "All":
        lazy = lazy.filter(pl.col("origin_country") == origin_country)
    if destination_country != "All":
        lazy = lazy.filter(pl.col("destination_country") == destination_country)
    return (
        lazy.filter(pl.col("departure_month_date").is_between(start_date, end_date, closed="both"))
        .filter(pl.col("cabin_class").is_in(cabin_classes))
        .collect()
    )


def apply_fleet_filters(fleet_df: pl.DataFrame, selected_models: list[str]) -> pl.DataFrame:
    if not selected_models:
        return fleet_df
    return fleet_df.lazy().filter(pl.col("model").is_in(selected_models)).collect()


def aggregate_routes(df: pl.DataFrame) -> pl.DataFrame:
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
        df.lazy()
        .group_by(group_cols)
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("fare_revenue").sum().alias("fare_revenue"),
            pl.col("tax_revenue").sum().alias("tax_revenue"),
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias("avg_ticket_value"),
            # Yield = average fare per distance unit / per flight minute. Using the average
            # fare (not cumulative revenue) makes this a real per-trip yield, and the guards
            # avoid inf/NaN if a route ever has zero distance or duration.
            pl.when(pl.col("distance") > 0)
            .then(pl.col("total_revenue") / pl.col("tickets_sold") / pl.col("distance"))
            .alias("fare_per_distance"),
            pl.when(pl.col("flight_minutes") > 0)
            .then(pl.col("total_revenue") / pl.col("tickets_sold") / pl.col("flight_minutes"))
            .alias("fare_per_minute"),
            route_label_expr(),
        )
        .sort("total_revenue", descending=True)
        .collect()
    )


def aggregate_city_pairs(route_df: pl.DataFrame) -> pl.DataFrame:
    """Combine both directions of a route into one unordered city pair (A and B).

    route_code is directional, so A to B and B to A are separate rows. We sum both
    directions and label each endpoint as "City (CODE)" so the chart is readable.
    Full airport names are too long to fit, so we use the city name plus the IATA code.
    """
    labelled = route_df.with_columns(
        (pl.col("origin_city") + " (" + pl.col("origin") + ")").alias("origin_label"),
        (pl.col("destination_city") + " (" + pl.col("destination") + ")").alias("destination_label"),
    )
    first_is_origin = pl.col("origin") <= pl.col("destination")
    return (
        labelled.lazy()
        .with_columns(
            pl.when(first_is_origin).then(pl.col("origin_label")).otherwise(pl.col("destination_label")).alias("end_a"),
            pl.when(first_is_origin).then(pl.col("destination_label")).otherwise(pl.col("origin_label")).alias("end_b"),
        )
        .group_by("end_a", "end_b")
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
        )
        .with_columns((pl.col("end_a") + " and " + pl.col("end_b")).alias("city_pair"))
        .sort("total_revenue", descending=True)
        .collect()
    )


def aggregate_monthly(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.lazy()
        .group_by("departure_month_date", "departure_year", "departure_month", "cabin_class")
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("fare_revenue").sum().alias("fare_revenue"),
            pl.col("tax_revenue").sum().alias("tax_revenue"),
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias("avg_ticket_value"),
            cabin_name_expr(),
        )
        .sort("departure_month_date", "cabin_class")
        .collect()
    )


def aggregate_cabins(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.lazy()
        .group_by("cabin_class")
        .agg(
            pl.col("tickets_sold").sum().alias("tickets_sold"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("fare_revenue").sum().alias("fare_revenue"),
            pl.col("tax_revenue").sum().alias("tax_revenue"),
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias("avg_ticket_value"),
            cabin_name_expr(),
        )
        .sort("total_revenue", descending=True)
        .collect()
    )


def fleet_by_model(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.lazy()
        .group_by("model")
        .agg(
            pl.len().alias("aircraft"),
            pl.col("scheduled_flights").sum().alias("scheduled_flights"),
            pl.col("scheduled_distance").sum().alias("scheduled_distance"),
            pl.col("scheduled_flight_hours").sum().alias("scheduled_flight_hours"),
            pl.col("estimated_fuel_gallons").sum().alias("estimated_fuel_gallons"),
        )
        .sort("scheduled_flights", descending=True)
        .collect()
    )


def money(value: float) -> str:
    def compact(amount: float, suffix: str) -> str:
        rounded = round(amount, 1)
        if rounded.is_integer():
            return f"{rounded:,.0f}{suffix}"
        return f"{rounded:,.1f}{suffix}"

    if value >= 1_000_000_000:
        return f"${compact(value / 1_000_000_000, 'B')}"
    if value >= 1_000_000:
        return f"${compact(value / 1_000_000, 'M')}"
    return f"${value:,.0f}"


def number(value: float | int) -> str:
    return f"{value:,.0f}"


def style_plot(fig):
    fig.update_layout(
        font_family="Inter, Arial, sans-serif",
        font_color="#E8EEF8",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=30),
        legend_title_text="",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.15)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.15)")
    return fig


st.markdown(
    """
    <style>
    html, body, [class*="css"], .stApp {
        font-family: Inter, Arial, sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
    }
    div[data-testid="stMetric"] {
        background: #0000FF; /* ELECTRIC accent from the color scheme */
        border: none;
        border-radius: 8px;
        padding: 0.7rem 0.85rem;
    }
    div[data-testid="stMetric"] label {
        color: rgba(255, 255, 255, 0.85);
        font-size: 0.78rem;
    }
    div[data-testid="stMetricValue"] {
        color: #FFFFFF;
        font-size: 1.35rem;
        line-height: 1.2;
    }
    div[data-testid="stMetricDelta"] {
        color: rgba(255, 255, 255, 0.85);
        font-size: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

require_data_files()

route_monthly_df = load_parquet(ROUTE_MONTHLY_PATH)
fleet_df = load_parquet(FLEET_PATH)

st.title("ATT Plane Route Revenue and Network Performance")
st.caption("Schema ATTGRP6 | Prepared from DB2 with Polars | Streamlit dashboard")

st.sidebar.header("Commercial Filters")
top_n = st.sidebar.slider("Top routes", min_value=5, max_value=25, value=10)

origin_continent = select_all_filter(
    "Origin continent",
    sorted_values(route_monthly_df, "origin_continent"),
)
destination_continent = select_all_filter(
    "Destination continent",
    sorted_values(route_monthly_df, "destination_continent"),
)
origin_country = select_all_filter(
    "Origin country",
    sorted_values(route_monthly_df, "origin_country"),
)
destination_country = select_all_filter(
    "Destination country",
    sorted_values(route_monthly_df, "destination_country"),
)

all_cabins = sorted_values(route_monthly_df, "cabin_class")
selected_cabins = st.sidebar.multiselect(
    "Cabin class",
    all_cabins,
    default=all_cabins,
    format_func=lambda value: CABIN_LABELS.get(value, value),
)
if not selected_cabins:
    selected_cabins = all_cabins

min_month = route_monthly_df.select(pl.min("departure_month_date")).item()
max_month = route_monthly_df.select(pl.max("departure_month_date")).item()
# Default the range to the last COMPLETE year so the partial final period (2026 is January
# only) does not skew the monthly trend. The user can still extend to the full max month.
last_full_year = (
    route_monthly_df.group_by("departure_year")
    .agg(pl.col("departure_month").n_unique().alias("n_months"))
    .filter(pl.col("n_months") >= 12)
    .select(pl.max("departure_year"))
    .item()
)
default_end = date(int(last_full_year), 12, 1) if last_full_year is not None else max_month
date_range = st.sidebar.date_input(
    "Departure month range",
    value=(min_month, default_end),
    min_value=min_month,
    max_value=max_month,
)
st.sidebar.caption(
    f"Default ends {default_end:%b %Y} (last complete year). "
    f"Data runs to {max_month:%b %Y}, which is partial."
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_month, end_month = date_range
else:
    start_month, end_month = min_month, max_month

st.sidebar.header("Fleet Filter")
all_models = sorted_values(fleet_df, "model")
selected_models = st.sidebar.multiselect("Aircraft model", all_models)

commercial_filtered = apply_commercial_filters(
    route_monthly_df,
    origin_continent,
    destination_continent,
    origin_country,
    destination_country,
    selected_cabins,
    start_month,
    end_month,
)
fleet_filtered = apply_fleet_filters(fleet_df, selected_models)

if commercial_filtered.is_empty() or fleet_filtered.is_empty():
    st.warning("No data matches the current filter selection.")
    st.stop()

route_filtered = aggregate_routes(commercial_filtered)
monthly_filtered = aggregate_monthly(commercial_filtered)
cabin_filtered = aggregate_cabins(commercial_filtered)
city_pairs = aggregate_city_pairs(route_filtered)

total_revenue = commercial_filtered.select(pl.sum("total_revenue")).item()
tickets_sold = commercial_filtered.select(pl.sum("tickets_sold")).item()
avg_ticket_value = total_revenue / tickets_sold if tickets_sold else 0
routes = route_filtered.select(pl.col("route_code").n_unique()).item()
aircraft = fleet_filtered.select(pl.col("aircraft_registration").n_unique()).item()

metric_cols = st.columns(5)
metric_cols[0].metric("Revenue", money(total_revenue))
metric_cols[1].metric("Tickets", number(tickets_sold))
metric_cols[2].metric("Avg ticket", money(avg_ticket_value))
metric_cols[3].metric("Routes", number(routes))
metric_cols[4].metric("Aircraft", number(aircraft))

top_pair = city_pairs.row(0, named=True)
best_yield_route = route_filtered.sort("fare_per_distance", descending=True, nulls_last=True).row(0, named=True)
top_cabin = cabin_filtered.row(0, named=True)

st.markdown(
    f"""
**Current readout:** the biggest city pair for the selected filters is `{top_pair["city_pair"]}` at {money(top_pair["total_revenue"])}, counting both directions.
The highest yield route (average fare per distance) is `{best_yield_route["origin"]}` to `{best_yield_route["destination"]}`.
Within the selected filters, the {top_cabin["cabin"]} cabin contributes the most revenue.
"""
)

tab_route, tab_time, tab_fleet, tab_data = st.tabs(
    ["Route Performance", "Time and Cabin", "Fleet Utilization", "Data"]
)

with tab_route:
    st.subheader("Top City Pairs by Revenue (both directions)")
    # Ascending sort so the largest pair sits at the top of the horizontal bar chart.
    top_pairs = city_pairs.head(top_n).sort("total_revenue", descending=False)
    fig_routes = px.bar(
        top_pairs.to_pandas(),
        x="total_revenue",
        y="city_pair",
        orientation="h",
        color="total_revenue",
        color_continuous_scale=BLUE_SCALE,
        labels={
            "city_pair": "City pair",
            "total_revenue": "Revenue",
        },
    )
    fig_routes.update_layout(coloraxis_showscale=False, yaxis_title="")
    fig_routes.update_yaxes(automargin=True)
    st.plotly_chart(style_plot(fig_routes), width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Revenue Efficiency")
        fig_efficiency = px.scatter(
            route_filtered.to_pandas(),
            x="distance",
            y="avg_ticket_value",
            size="tickets_sold",
            size_max=9,
            opacity=0.5,
            color="origin_continent",
            color_discrete_map=ranked_blue_map(route_filtered, "origin_continent", "total_revenue"),
            hover_name="route_label",
            labels={
                "distance": "Distance",
                "avg_ticket_value": "Average ticket value",
                "tickets_sold": "Tickets sold",
                "origin_continent": "Origin continent",
            },
        )
        fig_efficiency.update_traces(marker=dict(line=dict(width=0.25, color="#FFFFFF")))
        st.plotly_chart(style_plot(fig_efficiency), width="stretch")

    with right:
        st.subheader("Highest Yield Routes (fare per distance)")
        yield_table = (
            route_filtered.lazy()
            .select(
                "route_label",
                "tickets_sold",
                "total_revenue",
                "avg_ticket_value",
                "fare_per_distance",
                "fare_per_minute",
            )
            .sort("fare_per_distance", descending=True, nulls_last=True)
            .head(top_n)
            .collect()
        )
        st.dataframe(
            yield_table,
            width="stretch",
            hide_index=True,
            column_config={
                "total_revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
                "avg_ticket_value": st.column_config.NumberColumn("Avg fare", format="$%.2f"),
                "fare_per_distance": st.column_config.NumberColumn(
                    "Fare / distance",
                    format="$%.3f",
                ),
                "fare_per_minute": st.column_config.NumberColumn(
                    "Fare / minute",
                    format="$%.3f",
                ),
            },
        )

with tab_time:
    st.subheader("Monthly Revenue by Cabin")
    fig_monthly = px.line(
        monthly_filtered.to_pandas(),
        x="departure_month_date",
        y="total_revenue",
        color="cabin",
        color_discrete_map=ranked_blue_map(monthly_filtered, "cabin", "total_revenue"),
        markers=False,
        labels={
            "departure_month_date": "Departure month",
            "total_revenue": "Revenue",
            "cabin": "Cabin",
        },
    )
    st.plotly_chart(style_plot(fig_monthly), width="stretch")

    col_cabin, col_mix = st.columns(2)
    with col_cabin:
        st.subheader("Cabin Revenue Contribution")
        fig_cabin = px.bar(
            cabin_filtered.to_pandas(),
            x="cabin",
            y="total_revenue",
            color="total_revenue",
            color_continuous_scale=BLUE_SCALE,
            labels={"cabin": "Cabin", "total_revenue": "Revenue"},
        )
        fig_cabin.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(style_plot(fig_cabin), width="stretch")

    with col_mix:
        st.subheader("Cabin Ticket Mix")
        fig_mix = px.pie(
            cabin_filtered.to_pandas(),
            names="cabin",
            values="tickets_sold",
            hole=0.45,
            color="cabin",
            color_discrete_map=ranked_blue_map(cabin_filtered, "cabin", "tickets_sold"),
        )
        st.plotly_chart(style_plot(fig_mix), width="stretch")

with tab_fleet:
    model_summary = fleet_by_model(fleet_filtered)

    st.subheader("Scheduled Flights by Aircraft Model")
    fig_fleet = px.bar(
        model_summary.head(15).to_pandas(),
        x="model",
        y="scheduled_flights",
        color="scheduled_flights",
        color_continuous_scale=BLUE_SCALE,
        labels={
            "model": "Aircraft model",
            "scheduled_flights": "Scheduled flights",
        },
    )
    # Bars are sorted by scheduled flights and colored by the same value (tallest = brightest).
    # The model names on the x axis identify each bar, so the color bar is hidden as noise.
    fig_fleet.update_layout(xaxis_tickangle=-35, coloraxis_showscale=False)
    st.plotly_chart(style_plot(fig_fleet), width="stretch")

    st.subheader("Aircraft Utilization and Maintenance Exposure")
    fig_maintenance = px.scatter(
        fleet_filtered.to_pandas(),
        x="maintenance_flight_hours",
        y="scheduled_flights",
        size="scheduled_distance",
        size_max=8,
        opacity=0.45,
        hover_name="aircraft_registration",
        labels={
            "maintenance_flight_hours": "Maintenance flight hours",
            "scheduled_flights": "Scheduled flights",
            "scheduled_distance": "Scheduled distance",
        },
    )
    fig_maintenance.update_traces(marker=dict(color=CYAN, line=dict(width=0.2, color="#FFFFFF")))
    st.plotly_chart(style_plot(fig_maintenance), width="stretch")

    st.dataframe(
        fleet_filtered.select(
            "aircraft_registration",
            "model",
            "seat_capacity",
            "scheduled_flights",
            "scheduled_distance",
            "scheduled_flight_hours",
            "maintenance_takeoffs",
            "maintenance_flight_hours",
            "routes_served",
        ).sort("scheduled_flights", descending=True),
        width="stretch",
        hide_index=True,
    )

with tab_data:
    st.subheader("Route Summary")
    st.dataframe(
        route_filtered.select(
            "route_code",
            "origin",
            "destination",
            "origin_country",
            "destination_country",
            "distance",
            "flight_minutes",
            "tickets_sold",
            "total_revenue",
            "avg_ticket_value",
            "fare_per_distance",
        ).sort("total_revenue", descending=True),
        width="stretch",
        hide_index=True,
    )
