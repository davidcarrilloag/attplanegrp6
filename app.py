from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

st.set_page_config(
    page_title="ATT Plane | Revenue & Network Performance",
    page_icon="✈️",
    layout="wide",
)

DATA_DIR = Path("data")
ROUTE_MONTHLY_PATH = DATA_DIR / "route_monthly_revenue.parquet"
FLEET_PATH = DATA_DIR / "fleet_utilization.parquet"
CAPACITY_PATH = DATA_DIR / "route_capacity.parquet"

MONEY_COLUMNS = {
    "total_revenue",
    "fare_revenue",
    "tax_revenue",
    "avg_ticket_value",
    "computed_avg_ticket_value",
    "revenue_per_distance",
    "revenue_per_flight_minute",
}

# Ticket CLASS codes B/E/P do not follow intuitive names. A data review showed three clear
# fare levels (B lowest, E middle, P highest); we label by neutral fare tier and keep the
# apparent class name in parentheses.
CABIN_LABELS = {
    "B": "Lower fare (Business)",
    "E": "Mid fare (Economy)",
    "P": "Higher fare (Premium)",
}

# ---------------------------------------------------------------------------
# Design system: a single, restrained palette is the source of truth for every
# color in the app so the dashboard reads as one coherent, professional product.
# ---------------------------------------------------------------------------
INK = "#F4F6FB"          # app background (light)
SURFACE = "#FFFFFF"      # cards / panels
SURFACE_2 = "#F1F5FB"    # raised surface / hover
BORDER = "#E2E8F0"       # hairline borders
TEXT = "#0F1B2D"         # primary text (near-black navy)
MUTED = "#64748B"        # secondary text / axes (slate)

ACCENT = "#2563EB"       # primary accent (confident blue)
CYAN = "#0891B2"         # teal highlight (readable on white)
EMERALD = "#059669"
VIOLET = "#7C3AED"
AMBER = "#D97706"
PINK = "#DB2777"

# Categorical colorway (legends, multi-series) — blue / teal / amber + cool extras.
CATEGORICAL = [ACCENT, "#0D9488", "#F59E0B", "#1E3A8A", "#6366F1", "#DB2777"]

# Sequential magnitude scale (low -> high): light blue to deep navy. Bigger = darker / more
# saturated, which reads best on a light background.
SEQ = ["#DBEAFE", "#93C5FD", "#3B82F6", "#2563EB", "#1E3A8A"]

# One stable color per fare tier — a clean light->dark blue ramp (no dull gray), so the
# ordinal tiers read at a glance while staying executive.
TIER_COLORS = {
    "Lower fare (Business)": "#93C5FD",   # light blue
    "Mid fare (Economy)": "#3B82F6",      # blue (the dominant tier)
    "Higher fare (Premium)": "#1E3A8A",   # deep navy
}
# One stable color per origin continent — distinct but sober: blue / teal / amber.
CONTINENT_COLORS = {
    "EUROPE": "#2563EB", "AMERICA": "#0D9488", "ASIA": "#F59E0B",
    "AFRICA": "#7C3AED", "OCEANIA": "#DB2777",
}


def _to_colorscale(colors: list[str]) -> list[list]:
    n = len(colors)
    return [[i / (n - 1), c] for i, c in enumerate(colors)]


# ---------------------------------------------------------------------------
# Plotly template — registered once, applied to every figure for consistency.
# ---------------------------------------------------------------------------
FONT = "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
_AXIS = dict(
    gridcolor="rgba(15,27,45,0.07)",
    zeroline=False,
    linecolor="rgba(15,27,45,0.14)",
    tickfont=dict(color=MUTED, size=11),
    title=dict(font=dict(color=MUTED, size=12)),
    automargin=True,
)
pio.templates["attplane"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, size=13, color=TEXT),
        colorway=CATEGORICAL,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=12, t=14, b=8),
        hoverlabel=dict(
            bgcolor=SURFACE_2,
            bordercolor=BORDER,
            font=dict(color=TEXT, size=12, family=FONT),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            title_text="", font=dict(color=MUTED, size=12),
        ),
        xaxis={**_AXIS, "ticks": "outside", "tickcolor": "rgba(15,27,45,0.14)"},
        yaxis=_AXIS,
        colorscale=dict(sequential=_to_colorscale(SEQ)),
    )
)
pio.templates.default = "attplane"
px.defaults.template = "attplane"


def finalize(fig: go.Figure, height: int = 360, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        showlegend=legend,
        margin=dict(l=8, r=12, t=24 if legend else 12, b=8),
    )
    return fig


# ---------------------------------------------------------------------------
# Data loading + Polars transformations (logic unchanged from the team build)
# ---------------------------------------------------------------------------
@st.cache_data
def load_parquet(path: Path) -> pl.DataFrame:
    df = pl.read_parquet(path)
    decimal_columns = [col for col in MONEY_COLUMNS if col in df.columns]
    if decimal_columns:
        df = df.with_columns(pl.col(decimal_columns).cast(pl.Float64))
    return df


def require_data_files() -> None:
    missing = [str(p) for p in [ROUTE_MONTHLY_PATH, FLEET_PATH] if not p.exists()]
    if missing:
        st.error("Prepared data files are missing.")
        st.code("\n".join(["python prepare_data.py", "", "Missing:"] + missing))
        st.stop()


def sorted_values(df: pl.DataFrame, column: str) -> list[str]:
    return df.select(pl.col(column).drop_nulls().unique().sort()).to_series().to_list()


def cabin_name_expr() -> pl.Expr:
    return (
        pl.when(pl.col("cabin_class") == "B").then(pl.lit("Lower fare (Business)"))
        .when(pl.col("cabin_class") == "E").then(pl.lit("Mid fare (Economy)"))
        .when(pl.col("cabin_class") == "P").then(pl.lit("Higher fare (Premium)"))
        .otherwise(pl.col("cabin_class"))
        .alias("cabin")
    )


def route_label_expr() -> pl.Expr:
    return (
        pl.col("origin") + " → " + pl.col("destination") + "  (" + pl.col("route_code") + ")"
    ).alias("route_label")


def apply_commercial_filters(
    df, origin_continent, destination_continent, origin_country,
    destination_country, cabin_classes, start_date, end_date,
) -> pl.DataFrame:
    lazy = df.lazy()
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


def apply_fleet_filters(fleet_df, selected_models) -> pl.DataFrame:
    if not selected_models:
        return fleet_df
    return fleet_df.lazy().filter(pl.col("model").is_in(selected_models)).collect()


def aggregate_routes(df: pl.DataFrame) -> pl.DataFrame:
    group_cols = [
        "route_code", "origin", "destination", "origin_city", "origin_country",
        "origin_continent", "destination_city", "destination_country",
        "destination_continent", "distance", "flight_minutes",
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
        .with_columns((pl.col("end_a") + "  ↔  " + pl.col("end_b")).alias("city_pair"))
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
        )
        .with_columns(
            (pl.col("total_revenue") / pl.col("tickets_sold")).alias("avg_ticket_value"),
            cabin_name_expr(),
        )
        .sort("total_revenue", descending=True)
        .collect()
    )


def aggregate_origin_airports(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.lazy()
        .group_by(
            "origin", "origin_city", "origin_country", "origin_continent",
            "origin_latitude", "origin_longitude",
        )
        .agg(
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("tickets_sold").sum().alias("tickets_sold"),
        )
        .sort("total_revenue", descending=True)
        .collect()
    )


def top_routes_geo(df: pl.DataFrame, n: int) -> pl.DataFrame:
    return (
        df.lazy()
        .group_by(
            "route_code", "origin", "destination",
            "origin_latitude", "origin_longitude",
            "destination_latitude", "destination_longitude",
        )
        .agg(pl.col("total_revenue").sum().alias("total_revenue"))
        .sort("total_revenue", descending=True)
        .head(n)
        .collect()
    )


def fleet_by_model(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.lazy()
        .group_by("model")
        .agg(
            pl.len().alias("aircraft"),
            pl.col("seat_capacity").mean().alias("avg_seats"),
            pl.col("scheduled_flights").sum().alias("scheduled_flights"),
            pl.col("scheduled_distance").sum().alias("scheduled_distance"),
            pl.col("scheduled_flight_hours").sum().alias("scheduled_flight_hours"),
            pl.col("estimated_fuel_gallons").sum().alias("estimated_fuel_gallons"),
            pl.col("maintenance_flight_hours").mean().alias("avg_maint_hours"),
        )
        .sort("scheduled_flights", descending=True)
        .collect()
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def money(value: float) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.1f}K"
    return f"${value:,.0f}"


def number(value: float | int) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.0f}K"
    return f"{value:,.0f}"


# ---------------------------------------------------------------------------
# Global CSS — typography, KPI cards, panels, tabs, sidebar
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp {{ font-family: {FONT}; }}
    .stApp {{ background: {INK}; }}
    #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}
    .block-container {{ padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1500px; }}

    /* ---- Hero header ---- */
    .hero {{ margin: 0 0 0.2rem 0; }}
    .eyebrow {{
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;
        color: {ACCENT}; margin: 0 0 7px;
    }}
    .hero h1 {{
        font-size: 1.55rem; font-weight: 700; letter-spacing: -0.015em;
        color: {TEXT}; margin: 0; line-height: 1.2;
    }}
    .hero p {{ color: {MUTED}; font-size: 0.9rem; margin: 0.4rem 0 0; max-width: 760px; line-height: 1.5; }}
    .rule {{ height:1px; background:{BORDER}; margin: 0.9rem 0 0.2rem; }}

    /* ---- KPI strip: one flat panel divided by hairlines (financial-report style) ---- */
    .kpi-strip {{
        display:flex; align-items:stretch; background:{SURFACE};
        border:1px solid {BORDER}; border-radius:10px; margin: 1.0rem 0 0.2rem;
        box-shadow: 0 1px 2px rgba(15,27,45,0.04);
    }}
    .kpi {{ flex:1; padding: 16px 22px; }}
    .kpi-sep {{ width:1px; background:{BORDER}; margin: 14px 0; }}
    .kpi-label {{ font-size:0.67rem; letter-spacing:0.11em; text-transform:uppercase; color:{MUTED}; font-weight:600; }}
    .kpi-value {{ font-size:1.5rem; font-weight:700; color:{TEXT}; margin-top:8px; line-height:1.0; letter-spacing:-0.01em; font-variant-numeric: tabular-nums; }}
    .kpi-sub {{ font-size:0.73rem; color:{MUTED}; margin-top:5px; }}

    /* ---- Insight callout ---- */
    .callout {{
        background: {SURFACE};
        border: 1px solid {BORDER}; border-left: 3px solid {ACCENT};
        border-radius: 10px; padding: 13px 18px; margin: 0.7rem 0 0.2rem;
        color: {TEXT}; font-size: 0.9rem; line-height: 1.6;
    }}
    .callout b {{ color: {TEXT}; font-weight: 600; }}
    .callout .tag {{
        color:{MUTED}; font-weight:700; letter-spacing:0.12em; font-size:0.68rem;
        text-transform:uppercase; margin-right:4px;
    }}

    /* ---- Panel headers (above each chart) ---- */
    .panel-title {{
        font-size:0.95rem; font-weight:600; color:{TEXT}; margin: 0 0 0.12rem;
        position:relative; padding-left:11px;
    }}
    .panel-title::before {{
        content:''; position:absolute; left:0; top:2px; bottom:2px; width:3px;
        background:{ACCENT}; border-radius:2px;
    }}
    .panel-sub {{ font-size:0.78rem; color:{MUTED}; margin: 0 0 0.65rem; padding-left:11px; }}

    /* bordered chart panels */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: {SURFACE}; border-radius: 10px !important;
        border: 1px solid {BORDER} !important;
        box-shadow: 0 1px 2px rgba(15,27,45,0.04);
    }}

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid {BORDER}; }}
    .stTabs [data-baseweb="tab"] {{
        height: 44px; padding: 0 18px; color: {MUTED}; font-weight: 600; font-size:0.92rem;
        background: transparent;
    }}
    .stTabs [aria-selected="true"] {{ color: {TEXT} !important; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background: {ACCENT}; height: 2.5px; }}

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
    section[data-testid="stSidebar"] h2 {{
        font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.10em;
        color: {MUTED}; font-weight: 700;
    }}

    /* dataframes */
    div[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 12px; }}
    hr {{ border-color: {BORDER}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def panel_header(title: str, subtitle: str | None = None) -> None:
    html = f"<div class='panel-title'>{title}</div>"
    if subtitle:
        html += f"<div class='panel-sub'>{subtitle}</div>"
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Load + sidebar filters
# ---------------------------------------------------------------------------
require_data_files()
route_monthly_df = load_parquet(ROUTE_MONTHLY_PATH)
fleet_df = load_parquet(FLEET_PATH)
capacity_df = load_parquet(CAPACITY_PATH) if CAPACITY_PATH.exists() else None


def filter_geo(df: pl.DataFrame, oc: str, dc: str, ocn: str, dcn: str) -> pl.DataFrame:
    """Apply the geographic sidebar filters to a route-level frame."""
    lazy = df.lazy()
    if oc != "All":
        lazy = lazy.filter(pl.col("origin_continent") == oc)
    if dc != "All":
        lazy = lazy.filter(pl.col("destination_continent") == dc)
    if ocn != "All":
        lazy = lazy.filter(pl.col("origin_country") == ocn)
    if dcn != "All":
        lazy = lazy.filter(pl.col("destination_country") == dcn)
    return lazy.collect()

with st.sidebar:
    st.markdown("## Filters")
    top_n = st.slider("Top N (routes / pairs)", 5, 25, 10)

    origin_continent = st.selectbox("Origin continent", ["All"] + sorted_values(route_monthly_df, "origin_continent"))
    destination_continent = st.selectbox("Destination continent", ["All"] + sorted_values(route_monthly_df, "destination_continent"))
    origin_country = st.selectbox("Origin country", ["All"] + sorted_values(route_monthly_df, "origin_country"))
    destination_country = st.selectbox("Destination country", ["All"] + sorted_values(route_monthly_df, "destination_country"))

    all_cabins = sorted_values(route_monthly_df, "cabin_class")
    selected_cabins = st.multiselect(
        "Fare tier", all_cabins, default=all_cabins,
        format_func=lambda v: CABIN_LABELS.get(v, v),
    )
    if not selected_cabins:
        selected_cabins = all_cabins

    min_month = route_monthly_df.select(pl.min("departure_month_date")).item()
    max_month = route_monthly_df.select(pl.max("departure_month_date")).item()
    last_full_year = (
        route_monthly_df.group_by("departure_year")
        .agg(pl.col("departure_month").n_unique().alias("n_months"))
        .filter(pl.col("n_months") >= 12)
        .select(pl.max("departure_year"))
        .item()
    )
    default_end = date(int(last_full_year), 12, 1) if last_full_year is not None else max_month
    date_range = st.date_input(
        "Departure month range", value=(min_month, default_end),
        min_value=min_month, max_value=max_month,
    )
    st.caption(f"Default ends {default_end:%b %Y} (last full year). Data runs to {max_month:%b %Y}, which is partial.")
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_month, end_month = date_range
    else:
        start_month, end_month = min_month, max_month

    st.markdown("## Fleet")
    all_models = sorted_values(fleet_df, "model")
    selected_models = st.multiselect("Aircraft model", all_models)

commercial_filtered = apply_commercial_filters(
    route_monthly_df, origin_continent, destination_continent,
    origin_country, destination_country, selected_cabins, start_month, end_month,
)
fleet_filtered = apply_fleet_filters(fleet_df, selected_models)

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Airline Operations &middot; Group 6</div>
      <h1>Revenue &amp; Network Performance</h1>
      <p>Where revenue concentrates across routes, cabins, time and the fleet &mdash;
         schema ATTGRP6, prepared from DB2 with Polars.</p>
    </div>
    <div class="rule"></div>
    """,
    unsafe_allow_html=True,
)

if commercial_filtered.is_empty() or fleet_filtered.is_empty():
    st.warning("No data matches the current filter selection. Widen the filters in the sidebar.")
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

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
kpis = [
    ("Total revenue", money(total_revenue), f"{number(tickets_sold)} tickets"),
    ("Tickets sold", number(tickets_sold), "across all tiers"),
    ("Avg ticket value", f"${avg_ticket_value:,.0f}", "revenue / ticket"),
    ("Active routes", number(routes), "directional"),
    ("Aircraft in service", number(aircraft), "scheduled"),
]
parts: list[str] = []
for i, (label, value, sub) in enumerate(kpis):
    parts.append(
        f"<div class='kpi'><div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div><div class='kpi-sub'>{sub}</div></div>"
    )
    if i < len(kpis) - 1:
        parts.append("<div class='kpi-sep'></div>")
st.markdown(f"<div class='kpi-strip'>{''.join(parts)}</div>", unsafe_allow_html=True)

top_pair = city_pairs.row(0, named=True)
best_yield_route = route_filtered.sort("fare_per_distance", descending=True, nulls_last=True).row(0, named=True)
top_cabin = cabin_filtered.row(0, named=True)
st.markdown(
    f"""
    <div class="callout">
      <span class="tag">Key takeaway</span>&nbsp; The biggest city pair is
      <b>{top_pair["city_pair"]}</b> at <b>{money(top_pair["total_revenue"])}</b> (both directions).
      Highest yield route: <b>{best_yield_route["origin"]} &rarr; {best_yield_route["destination"]}</b>.
      The <b>{top_cabin["cabin"]}</b> tier contributes the most revenue in this selection.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Key findings & assumptions", expanded=False):
    st.markdown(
        """
**Main findings**

1. **Revenue is broadly distributed, not concentrated.** The top 10 of 157 city pairs make up
   only about 13% of revenue (the largest single pair is about 1.5%). The network carries low
   single-route dependency risk — a resilience story, not a "star route" story.
2. **The Mid-fare (Economy) tier is the revenue engine: about 77% of revenue (≈\$219B)** on the
   back of volume (≈170M of 248M tickets), despite only a mid-level average fare.
3. **The Higher-fare (Premium) tier earns the least (≈\$12B)** despite the highest average fare
   (≈\$1,770), because its volume is tiny (≈6.7M tickets) — a niche, high-margin segment.
4. **Average fare scales almost linearly with distance** — pricing is distance-driven, so
   yield (fare per km) is fairly flat across routes and is the better lever than raw revenue.
5. **Demand is strongly seasonal every year, and fuel burn per flight varies about 10x by aircraft**
   (regional jets vs widebodies), so the fleet mix — not just utilization — drives fuel cost.
6. **Capacity is uniformly well-utilised: about 83% load factor on every route** (a tight 81–84%
   band). Planes are already near-full network-wide, so the growth lever is stimulating demand on
   the seats we already fly (closing the gap to about 90%), not adding aircraft.

**Assumptions & scope**

- Revenue = `SUM(TICKETS.TOTAL_AMOUNT)` (fare + airport tax + local tax).
- Cabin codes `B`/`E`/`P` are relabelled by **fare tier** after a data review (the cheapest
  class is not the highest-volume one, so they do not behave like real cabins).
- Geography is attributed to the **origin** airport of each route.
- The 248M-row `TICKETS` table is aggregated **server-side** and prepared with Polars at
  `route x cabin x month` grain; raw tickets are never loaded into the app.
- `PASSENGERS` is excluded (PII; `VIPCARD` is entirely null in this schema).
- Data runs 2010-2026, but 2026 is January only, so the date filter defaults to the last full year.
        """
    )

tab_route, tab_time, tab_cap, tab_fleet, tab_data = st.tabs(
    ["  Route Performance  ", "  Time & Cabin  ", "  Capacity  ", "  Fleet  ", "  Data  "]
)

# ===========================================================================
# TAB 1 — ROUTE PERFORMANCE
# ===========================================================================
with tab_route:
    map_col, bar_col = st.columns([1.35, 1])

    with map_col:
        with st.container(border=True):
            panel_header("Network revenue map", "Bubble size & color = revenue by origin airport. Lines = top route flows.")
            airports = aggregate_origin_airports(commercial_filtered)
            routes_geo = top_routes_geo(commercial_filtered, max(top_n, 12))

            fig_map = go.Figure()
            # route flow lines (drawn first, behind the bubbles)
            lon_seg, lat_seg = [], []
            for r in routes_geo.iter_rows(named=True):
                lon_seg += [r["origin_longitude"], r["destination_longitude"], None]
                lat_seg += [r["origin_latitude"], r["destination_latitude"], None]
            fig_map.add_trace(go.Scattergeo(
                lon=lon_seg, lat=lat_seg, mode="lines",
                line=dict(width=1, color="rgba(37,99,235,0.28)"),
                hoverinfo="skip", showlegend=False,
            ))
            ap = airports.to_pandas()
            max_rev = ap["total_revenue"].max() or 1
            fig_map.add_trace(go.Scattergeo(
                lon=ap["origin_longitude"], lat=ap["origin_latitude"], mode="markers",
                marker=dict(
                    size=ap["total_revenue"], sizemode="area",
                    sizeref=2.0 * max_rev / (42.0 ** 2), sizemin=4,
                    color=ap["total_revenue"], colorscale=_to_colorscale(SEQ),
                    line=dict(width=0.6, color="rgba(255,255,255,0.85)"), opacity=0.92,
                    showscale=False,
                ),
                text=ap["origin_city"], customdata=ap[["origin_country", "tickets_sold", "total_revenue"]],
                hovertemplate="<b>%{text}</b>, %{customdata[0]}<br>Revenue: %{customdata[2]:$,.0f}<br>Tickets: %{customdata[1]:,}<extra></extra>",
                showlegend=False,
            ))
            fig_map.update_geos(
                projection_type="natural earth", bgcolor="rgba(0,0,0,0)",
                showland=True, landcolor="#E9EEF6", showcountries=True, countrycolor="#CBD5E1",
                showcoastlines=False, showframe=False, showocean=False,
                lataxis_range=[-55, 80],
            )
            fig_map.update_layout(height=430, margin=dict(l=0, r=0, t=6, b=0))
            st.plotly_chart(fig_map, width="stretch")

    with bar_col:
        with st.container(border=True):
            panel_header(
                "Revenue concentration",
                "Cumulative share of revenue as routes are added (ranked high to low). "
                "The closer the curve sits to the dashed even-split line, the more evenly "
                "revenue is spread across the network.",
            )
            pareto = (
                city_pairs.sort("total_revenue", descending=True)
                .select("city_pair", "total_revenue")
                .with_columns(pl.col("total_revenue").cum_sum().alias("cum"))
            )
            grand_total = pareto.select(pl.col("total_revenue").sum()).item() or 1
            pareto = pareto.with_columns(
                (pl.col("cum") / grand_total * 100).alias("cum_pct"),
                pl.int_range(1, pl.len() + 1).alias("rank"),
            )
            n_pairs = pareto.height
            ranks = [0] + pareto["rank"].to_list()
            cum = [0.0] + pareto["cum_pct"].to_list()
            cum_by_rank = dict(zip(pareto["rank"].to_list(), pareto["cum_pct"].to_list()))

            fig_conc = go.Figure()
            fig_conc.add_trace(go.Scatter(
                x=[0, n_pairs], y=[0, 100], mode="lines",
                line=dict(color=MUTED, width=1, dash="dash"),
                name="Even split", hoverinfo="skip",
            ))
            fig_conc.add_trace(go.Scatter(
                x=ranks, y=cum, mode="lines", fill="tozeroy",
                line=dict(color=ACCENT, width=2.5), fillcolor="rgba(37,99,235,0.12)",
                name="Cumulative revenue",
                hovertemplate="Top %{x} routes &rarr; %{y:.1f}% of revenue<extra></extra>",
            ))
            for k in (10, 25):
                if k < n_pairs:
                    yk = cum_by_rank[k]
                    fig_conc.add_trace(go.Scatter(
                        x=[k], y=[yk], mode="markers+text",
                        marker=dict(color=ACCENT, size=9, line=dict(color="#FFFFFF", width=1.5)),
                        text=[f"  Top {k} = {yk:.0f}%"], textposition="middle right",
                        textfont=dict(color=TEXT, size=11), cliponaxis=False,
                        showlegend=False, hoverinfo="skip",
                    ))
            fig_conc.update_xaxes(title=f"Routes ranked by revenue (of {n_pairs})", rangemode="tozero")
            fig_conc.update_yaxes(title="Cumulative revenue", ticksuffix="%", range=[0, 101])
            st.plotly_chart(finalize(fig_conc, height=430, legend=True), width="stretch")

    left, right = st.columns([1, 1])
    with left:
        with st.container(border=True):
            panel_header("Average fare vs distance", "Each bubble is a route. Size = tickets sold, color = origin continent.")
            rf = route_filtered.to_pandas()
            fig_eff = px.scatter(
                rf, x="distance", y="avg_ticket_value", size="tickets_sold", size_max=26,
                color="origin_continent", color_discrete_map=CONTINENT_COLORS,
                hover_name="route_label", custom_data=["tickets_sold", "total_revenue"],
                labels={"distance": "Distance (km)", "avg_ticket_value": "Avg ticket ($)", "origin_continent": "Origin"},
            )
            fig_eff.update_traces(
                marker=dict(opacity=0.82, line=dict(width=0.5, color="rgba(15,27,45,0.20)")),
                hovertemplate="<b>%{hovertext}</b><br>Distance: %{x:,} km<br>Avg fare: %{y:$,.0f}<br>Tickets: %{customdata[0]:,}<extra></extra>",
            )
            fig_eff.update_yaxes(tickprefix="$")
            st.plotly_chart(finalize(fig_eff, height=380, legend=True), width="stretch")

    with right:
        with st.container(border=True):
            panel_header("Highest-yield routes", "Average fare per km — pricing power, independent of distance.")
            yield_table = (
                route_filtered.lazy()
                .select("route_label", "tickets_sold", "total_revenue", "avg_ticket_value", "fare_per_distance", "fare_per_minute")
                .sort("fare_per_distance", descending=True, nulls_last=True)
                .head(top_n)
                .collect()
            )
            st.dataframe(
                yield_table, width="stretch", hide_index=True, height=330,
                column_config={
                    "route_label": st.column_config.TextColumn("Route"),
                    "tickets_sold": st.column_config.NumberColumn("Tickets", format="%d"),
                    "total_revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
                    "avg_ticket_value": st.column_config.NumberColumn("Avg fare", format="$%.0f"),
                    "fare_per_distance": st.column_config.NumberColumn("$/km", format="$%.3f"),
                    "fare_per_minute": st.column_config.NumberColumn("$/min", format="$%.2f"),
                },
            )

# ===========================================================================
# TAB 2 — TIME & CABIN
# ===========================================================================
with tab_time:
    with st.container(border=True):
        panel_header("Monthly revenue by fare tier", "Stacked area — total height is total revenue; bands show the tier mix.")
        mf = monthly_filtered.to_pandas()
        mf["rev_b"] = mf["total_revenue"] / 1e9
        fig_month = px.area(
            mf, x="departure_month_date", y="rev_b", color="cabin",
            color_discrete_map=TIER_COLORS,
            labels={"departure_month_date": "", "rev_b": "Revenue ($B)", "cabin": "Fare tier"},
        )
        fig_month.update_traces(line=dict(width=0.8), hovertemplate="%{x|%b %Y}<br>$%{y:.2f}B<extra></extra>")
        fig_month.update_yaxes(tickprefix="$", ticksuffix="B")
        st.plotly_chart(finalize(fig_month, height=340, legend=True), width="stretch")

    c1, c2 = st.columns([1.4, 1])
    with c1:
        with st.container(border=True):
            panel_header("Monthly tickets by fare tier", "Volume tells the real story: the mid tier dominates demand.")
            fig_tix = px.line(
                mf, x="departure_month_date", y="tickets_sold", color="cabin",
                color_discrete_map=TIER_COLORS,
                labels={"departure_month_date": "", "tickets_sold": "Tickets", "cabin": "Fare tier"},
            )
            fig_tix.update_traces(line=dict(width=2), hovertemplate="%{x|%b %Y}<br>%{y:,} tickets<extra></extra>")
            fig_tix.update_yaxes(tickformat="~s")
            st.plotly_chart(finalize(fig_tix, height=330, legend=True), width="stretch")

    with c2:
        with st.container(border=True):
            panel_header("Ticket mix", "Share of tickets sold by tier.")
            cab = cabin_filtered.to_pandas()
            fig_mix = px.pie(
                cab, names="cabin", values="tickets_sold", hole=0.62,
                color="cabin", color_discrete_map=TIER_COLORS,
            )
            fig_mix.update_traces(
                textinfo="percent", textposition="outside",
                textfont=dict(color=TEXT, size=12, family=FONT),
                marker=dict(line=dict(color="#FFFFFF", width=2)),
                hovertemplate="<b>%{label}</b><br>%{value:,} tickets (%{percent})<extra></extra>",
            )
            fig_mix.add_annotation(text=f"<b>{number(tickets_sold)}</b><br><span style='color:{MUTED}'>tickets</span>",
                                   showarrow=False, font=dict(size=15, color=TEXT))
            st.plotly_chart(finalize(fig_mix, height=330, legend=True), width="stretch")

    with st.container(border=True):
        panel_header(
            "The revenue paradox: the cheapest fare earns the most",
            "Two aligned views, both starting at zero (no dual axis). The Mid tier earns "
            "the most revenue despite only a mid-level fare — it is volume, not price.",
        )
        cab2 = cabin_filtered.to_pandas()
        colors = [TIER_COLORS.get(c, ACCENT) for c in cab2["cabin"]]
        cab2["rev_label"] = cab2["total_revenue"].map(money)
        cab2["fare_label"] = cab2["avg_ticket_value"].map(lambda v: f"${v:,.0f}")
        col_rev, col_fare = st.columns(2)
        with col_rev:
            fig_rev = px.bar(cab2, x="cabin", y="total_revenue", text="rev_label",
                             labels={"cabin": "", "total_revenue": ""})
            fig_rev.update_traces(marker_color=colors, textposition="outside",
                                  textfont=dict(color=TEXT, size=12), cliponaxis=False,
                                  hovertemplate="<b>%{x}</b><br>Revenue: %{y:$,.0f}<extra></extra>")
            fig_rev.update_yaxes(visible=False)
            fig_rev.add_annotation(text="Total revenue", xref="paper", yref="paper", x=0, y=1.06,
                                   showarrow=False, font=dict(color=MUTED, size=12), xanchor="left")
            st.plotly_chart(finalize(fig_rev, height=330), width="stretch")
        with col_fare:
            fig_fare = px.bar(cab2, x="cabin", y="avg_ticket_value", text="fare_label",
                              labels={"cabin": "", "avg_ticket_value": ""})
            fig_fare.update_traces(marker_color=colors, textposition="outside",
                                   textfont=dict(color=TEXT, size=12), cliponaxis=False,
                                   hovertemplate="<b>%{x}</b><br>Avg fare: %{y:$,.0f}<extra></extra>")
            fig_fare.update_yaxes(visible=False)
            fig_fare.add_annotation(text="Average fare", xref="paper", yref="paper", x=0, y=1.06,
                                    showarrow=False, font=dict(color=MUTED, size=12), xanchor="left")
            st.plotly_chart(finalize(fig_fare, height=330), width="stretch")

# ===========================================================================
# TAB — CAPACITY / LOAD FACTOR
# ===========================================================================
with tab_cap:
    if capacity_df is None:
        st.info("Run `python prepare_data.py` to generate `data/route_capacity.parquet` for this view.")
    else:
        cap = filter_geo(capacity_df, origin_continent, destination_continent,
                         origin_country, destination_country)
        if cap.is_empty():
            st.warning("No routes match the current geographic filters.")
        else:
            agg = cap.select(
                pl.col("tickets_sold").sum().alias("tk"),
                pl.col("available_seats").sum().alias("seats"),
                pl.col("total_revenue").sum().alias("rev"),
            ).row(0, named=True)
            lf = agg["tk"] / agg["seats"] if agg["seats"] else 0
            avg_fare = agg["rev"] / agg["tk"] if agg["tk"] else 0
            target = 0.90
            extra_seats = max(0.0, agg["seats"] * target - agg["tk"])
            uplift = extra_seats * avg_fare

            st.markdown(
                f"""
                <div class="callout">
                  <span class="tag">Recommendation</span>&nbsp;
                  The network already flies at <b>{lf:.1%}</b> load factor, and remarkably every
                  route sits in a tight 81–84% band — capacity is well matched to demand everywhere.
                  The lever is therefore not filling planes but the <b>{(1 - lf):.0%} of seats still
                  empty</b>: closing the gap to a <b>{target:.0%}</b> target would sell about
                  <b>{number(extra_seats)}</b> more tickets, roughly <b>{money(uplift)}</b> of
                  incremental revenue at today's average fare — through demand stimulation on
                  existing capacity, not new aircraft.
                </div>
                """,
                unsafe_allow_html=True,
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("Avg load factor", f"{lf:.1%}")
            m2.metric("Seats offered", number(agg["seats"]))
            m3.metric("Empty-seat headroom to 90%", f"{number(extra_seats)}")

            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    panel_header(
                        "Load factor is uniformly high",
                        "Distribution of occupancy across routes — the tight cluster near "
                        f"{lf:.0%} means demand is consistently well served.",
                    )
                    cap_pd = cap.to_pandas()
                    fig_hist = px.histogram(cap_pd, x="load_factor", nbins=22)
                    fig_hist.update_traces(marker_color=ACCENT, marker_line_width=0,
                                           hovertemplate="LF %{x:.0%}<br>%{y} routes<extra></extra>")
                    fig_hist.add_vline(x=lf, line=dict(color=AMBER, width=2, dash="dash"),
                                       annotation_text=f"avg {lf:.0%}", annotation_position="top",
                                       annotation_font_color=MUTED)
                    fig_hist.update_xaxes(tickformat=".0%", title="Load factor")
                    fig_hist.update_yaxes(title="Routes")
                    st.plotly_chart(finalize(fig_hist, height=360), width="stretch")
            with c2:
                with st.container(border=True):
                    panel_header(
                        "Where the empty seats are",
                        "Routes with the most unsold seats (absolute) — the biggest targets to "
                        "stimulate demand on capacity we already fly.",
                    )
                    empty = (
                        cap.with_columns(
                            (pl.col("available_seats") - pl.col("tickets_sold")).alias("empty_seats"),
                            (pl.col("origin") + " → " + pl.col("destination")).alias("route_label"),
                        )
                        .sort("empty_seats", descending=True)
                        .head(top_n)
                        .sort("empty_seats")
                        .to_pandas()
                    )
                    empty["lbl"] = empty["empty_seats"].map(number)
                    fig_empty = px.bar(empty, x="empty_seats", y="route_label", orientation="h",
                                       color="empty_seats", color_continuous_scale=SEQ, text="lbl",
                                       labels={"route_label": "", "empty_seats": "Empty seats"})
                    fig_empty.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False,
                                            textfont=dict(color=TEXT, size=11),
                                            hovertemplate="<b>%{y}</b><br>%{x:,} empty seats<extra></extra>")
                    fig_empty.update_layout(coloraxis_showscale=False)
                    fig_empty.update_xaxes(visible=False)
                    st.plotly_chart(finalize(fig_empty, height=360), width="stretch")

# ===========================================================================
# TAB 3 — FLEET
# ===========================================================================
with tab_fleet:
    model_summary = fleet_by_model(fleet_filtered)

    f1, f2 = st.columns(2)
    with f1:
        with st.container(border=True):
            panel_header("Most-scheduled aircraft models", "Total scheduled flights by model (top 12).")
            ms = model_summary.head(12).sort("scheduled_flights").to_pandas()
            ms["label"] = ms["scheduled_flights"].map(number)
            fig_fleet = px.bar(
                ms, x="scheduled_flights", y="model", orientation="h",
                color="scheduled_flights", color_continuous_scale=SEQ, text="label",
                labels={"model": "", "scheduled_flights": "Scheduled flights"},
            )
            fig_fleet.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False,
                                    textfont=dict(color=TEXT, size=11),
                                    hovertemplate="<b>%{y}</b><br>%{x:,} flights<extra></extra>")
            fig_fleet.update_layout(coloraxis_showscale=False)
            fig_fleet.update_xaxes(visible=False)
            st.plotly_chart(finalize(fig_fleet, height=420), width="stretch")

    with f2:
        with st.container(border=True):
            panel_header("Fuel burned per flight", "Estimated gallons/flight — the fleet mix drives fuel cost.")
            fuel = (
                model_summary.lazy()
                .filter(pl.col("scheduled_flights") > 0)
                .with_columns((pl.col("estimated_fuel_gallons") / pl.col("scheduled_flights")).alias("fuel_per_flight"))
                .sort("fuel_per_flight", descending=True)
                .head(12)
                .collect()
                .sort("fuel_per_flight")
                .to_pandas()
            )
            fuel["label"] = fuel["fuel_per_flight"].map(lambda v: f"{v:,.0f}")
            fig_fuel = px.bar(
                fuel, x="fuel_per_flight", y="model", orientation="h",
                color="fuel_per_flight", color_continuous_scale=["#FEF3C7", "#F59E0B", "#B45309"],
                text="label", labels={"model": "", "fuel_per_flight": "Gallons / flight"},
            )
            fig_fuel.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT, size=11),
                                   hovertemplate="<b>%{y}</b><br>%{x:,.0f} gal/flight<extra></extra>")
            fig_fuel.update_layout(coloraxis_showscale=False)
            fig_fuel.update_xaxes(visible=False)
            st.plotly_chart(finalize(fig_fuel, height=420), width="stretch")

    with st.container(border=True):
        panel_header("Utilization vs maintenance exposure", "Each point is a model. X = scheduled flight hours, Y = avg maintenance hours, size = fleet count.")
        ms2 = model_summary.to_pandas()
        fig_util = px.scatter(
            ms2, x="scheduled_flight_hours", y="avg_maint_hours", size="aircraft", size_max=34,
            color="estimated_fuel_gallons", color_continuous_scale=SEQ, hover_name="model",
            labels={
                "scheduled_flight_hours": "Scheduled flight hours", "avg_maint_hours": "Avg maintenance hours",
                "aircraft": "Aircraft", "estimated_fuel_gallons": "Fuel (gal)",
            },
        )
        fig_util.update_traces(marker=dict(opacity=0.88, line=dict(width=0.5, color="rgba(15,27,45,0.20)")))
        fig_util.update_xaxes(tickformat="~s")
        fig_util.update_layout(coloraxis_colorbar=dict(title="Fuel", tickformat="~s"))
        st.plotly_chart(finalize(fig_util, height=380), width="stretch")

# ===========================================================================
# TAB 4 — DATA
# ===========================================================================
with tab_data:
    with st.container(border=True):
        panel_header("Route summary", "Directional routes, sorted by revenue. Download via the toolbar on hover.")
        st.dataframe(
            route_filtered.select(
                "route_code", "origin", "destination", "origin_country", "destination_country",
                "distance", "flight_minutes", "tickets_sold", "total_revenue",
                "avg_ticket_value", "fare_per_distance",
            ).sort("total_revenue", descending=True),
            width="stretch", hide_index=True, height=460,
            column_config={
                "route_code": st.column_config.TextColumn("Route"),
                "origin": "From", "destination": "To",
                "origin_country": "Origin country", "destination_country": "Dest. country",
                "distance": st.column_config.NumberColumn("Distance (km)", format="%d"),
                "flight_minutes": st.column_config.NumberColumn("Minutes", format="%d"),
                "tickets_sold": st.column_config.NumberColumn("Tickets", format="%d"),
                "total_revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
                "avg_ticket_value": st.column_config.NumberColumn("Avg fare", format="$%.0f"),
                "fare_per_distance": st.column_config.NumberColumn("$/km", format="$%.3f"),
            },
        )

        route_summary = route_filtered.select(
            "route_code", "origin", "destination", "origin_country", "destination_country",
            "distance", "flight_minutes", "tickets_sold", "total_revenue",
            "avg_ticket_value", "fare_per_distance",
        ).sort("total_revenue", descending=True)
        st.download_button(
            "Download route summary (CSV)",
            data=route_summary.write_csv(),
            file_name="attgrp6_route_revenue_summary.csv",
            mime="text/csv",
        )

    with st.container(border=True):
        panel_header("Fleet detail", "Per-aircraft scheduled utilization and maintenance.")
        st.dataframe(
            fleet_filtered.select(
                "aircraft_registration", "model", "seat_capacity", "scheduled_flights",
                "scheduled_distance", "scheduled_flight_hours", "maintenance_takeoffs",
                "maintenance_flight_hours", "routes_served",
            ).sort("scheduled_flights", descending=True),
            width="stretch", hide_index=True, height=380,
        )

st.markdown(
    f"<div style='color:{MUTED}; font-size:0.76rem; margin-top:1.2rem; "
    f"border-top:1px solid {BORDER}; padding-top:0.7rem;'>"
    "Source: ATTPLANE DB2 database, schema ATTGRP6 (TICKETS, ROUTES, AIRPORTS, FLIGHTS, "
    "AIRPLANES) &middot; aggregated server-side and prepared with Polars at route &times; cabin "
    "&times; month grain &middot; revenue = sum of ticket TOTAL_AMOUNT (fare + tax)."
    "</div>",
    unsafe_allow_html=True,
)
