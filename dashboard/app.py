

import os
import streamlit as st
import pandas as pd
import altair as alt
import clickhouse_connect
from dotenv import load_dotenv

st.set_page_config(
    page_title="Africa Pulse — City Intelligence Platform",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()


@st.cache_resource
def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def query_df(query: str) -> pd.DataFrame:
    client = get_clickhouse_client()
    return client.query_df(query)


def dedupe(df: pd.DataFrame, subset: list) -> pd.DataFrame:
    """
    Collapse reverse-merge duplicates before rendering.

    The marts are `ReplacingMergeTree`, whose background merges are asynchronous.
    A dashboard read can therefore see two physical rows for the same logical key.
    Every visualisation and metric card de-duplicates first so counts, column
    ratios (`st.columns(len(...))`) and bar charts always reflect logical rows.
    """
    if df.empty:
        return df
    return df.drop_duplicates(subset=subset).reset_index(drop=True)


def render_chart(chart, fallback_df: pd.DataFrame = None, fallback_index: str = None) -> None:
    """
    Render an Altair chart, degrading to a native Streamlit chart if the
    Vega-Lite spec cannot materialise (empty frame, locked altair version, etc.)
    so a broken visual never blanks the analytical page.
    """
    try:
        st.altair_chart(chart, use_container_width=True)
    except Exception as exc:  # pragma: no cover - defensive fallback path
        st.warning(f"Chart spec could not be rendered ({exc}). Falling back to tabular view.")
        if fallback_df is not None and not fallback_df.empty:
            if fallback_index and fallback_index in fallback_df.columns:
                st.bar_chart(fallback_df.set_index(fallback_index))
            else:
                st.dataframe(fallback_df, use_container_width=True)


st.sidebar.title("🌍 Africa Pulse")
st.sidebar.caption("Live African Urban Intelligence Platform")
st.sidebar.markdown("---")

nav_page = st.sidebar.radio(
    "Analytical Navigation",
    [
        "🏆 City Intelligence Index",
        "🚌 Mobility & Infrastructure",
        "🌱 Climate & Environment",
        "💱 Economic & FX Stability",
        "🔬 Cross-Domain Insights",
        "🛡️ Quality & Provenance Audit",
    ],
)

try:
    dim_cities_df = query_df("SELECT * FROM urbanpulse.dim_city ORDER BY country, city_name")
except Exception as e:
    st.error(f"Failed to connect to ClickHouse warehouse: {e}")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader("Monitored Metropolises")
for _, city in dim_cities_df.iterrows():
    st.sidebar.markdown(f"• **{city['city_name']}**, {city['country']} ({city['currency_code']})")

st.sidebar.info(
    "Data Source: Live ClickHouse Analytical Warehouse (`urbanpulse`)\n"
    "Architectural Engine: Native ClickHouse SQL Marts"
)



if nav_page == "🏆 City Intelligence Index":
    st.title("🏆 African City Intelligence Index (0–100)")
    st.markdown(
        """
        The **City Intelligence Score** is a composite metric combining real-time environmental observations,
        currency stability, mobility & infrastructure readiness, and public event vibrancy.
        
        **Formula Weighting:**
        - **Environment (30%):** PM2.5 air quality relative to WHO guidelines (24h clean-air score).
        - **Economic / FX (25%):** 24h currency rate volatility and depreciation penalty.
        - **Mobility (25%):** Transit & commercial node density per 15km urban catchment.
        - **News Vibrancy (20%):** Regional media and public event intensity share.
        """
    )

    df_ci = query_df("""
        SELECT 
            city_name,
            country,
            date,
            city_intelligence_score,
            score_environment,
            score_economic,
            score_mobility,
            score_vibrancy,
            avg_pm2_5,
            units_per_usd,
            transit_nodes
        FROM (SELECT * FROM urbanpulse.mart_city_intelligence_daily FINAL)
        ORDER BY date DESC, city_intelligence_score DESC
    """)

    # One logical row per (city, date) — never over-count on un-merged parts.
    df_ci = dedupe(df_ci, ["city_name", "date"])

    latest_date = df_ci["date"].max()
    latest_df = (
        df_ci[df_ci["date"] == latest_date]
        .sort_values("city_intelligence_score", ascending=False)
        .reset_index(drop=True)
        .copy()
    )
    latest_df.insert(0, "Rank", latest_df.index + 1)

    st.subheader(f"Latest Intelligence Standings — {latest_date}")
    st.caption(
        "Composite City Intelligence Score (0–100) = 0.30 × Environment + 0.25 × Economic/FX "
        "+ 0.25 × Mobility + 0.20 × News Vibrancy. Hover a card for the full pillar breakdown."
    )

    cols = st.columns(len(latest_df)) if not latest_df.empty else []
    for idx, (_, row) in enumerate(latest_df.iterrows()):
        with cols[idx]:
            st.metric(
                label=f"#{row['Rank']} {row['city_name']} ({row['country']})",
                value=f"{row['city_intelligence_score']:.1f} / 100",
                delta=f"Env {row['score_environment']:.0f} · FX {row['score_economic']:.0f}",
                delta_color="off",
                help=(
                    f"Environment {row['score_environment']:.1f} / 100 (weight 30%)\n\n"
                    f"Economic / FX stability {row['score_economic']:.1f} / 100 (weight 25%)\n\n"
                    f"Mobility readiness {row['score_mobility']:.1f} / 100 (weight 25%)\n\n"
                    f"News vibrancy {row['score_vibrancy']:.1f} / 100 (weight 20%)"
                ),
            )

    st.markdown("#### Composite Standings & Pillar Matrix")
    st.dataframe(
        latest_df[[
            "Rank",
            "city_name",
            "country",
            "city_intelligence_score",
            "score_environment",
            "score_economic",
            "score_mobility",
            "score_vibrancy",
        ]].rename(columns={
            "city_name": "City",
            "country": "Country",
            "city_intelligence_score": "Composite (0–100)",
            "score_environment": "Environment (30%)",
            "score_economic": "Economic / FX (25%)",
            "score_mobility": "Mobility (25%)",
            "score_vibrancy": "Vibrancy (20%)",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Composite (0–100)": st.column_config.ProgressColumn(
                "Composite (0–100)", min_value=0.0, max_value=100.0, format="%.1f"
            ),
            "Environment (30%)": st.column_config.NumberColumn("Environment (30%)", format="%.1f"),
            "Economic / FX (25%)": st.column_config.NumberColumn("Economic / FX (25%)", format="%.1f"),
            "Mobility (25%)": st.column_config.NumberColumn("Mobility (25%)", format="%.1f"),
            "Vibrancy (20%)": st.column_config.NumberColumn("Vibrancy (20%)", format="%.1f"),
        },
    )

    st.markdown("### Dimension Breakdown Comparison")

    PILLAR_WEIGHTS = {
        "score_environment": ("Environment", 0.30),
        "score_economic": ("Economic / FX", 0.25),
        "score_mobility": ("Mobility", 0.25),
        "score_vibrancy": ("News Vibrancy", 0.20),
    }
    PILLAR_ORDER = [label for label, _ in PILLAR_WEIGHTS.values()]
    city_order = latest_df["city_name"].tolist()

    subscores_df = latest_df.melt(
        id_vars=["city_name"],
        value_vars=list(PILLAR_WEIGHTS.keys()),
        var_name="Pillar",
        value_name="Score",
    )
    subscores_df["Weight"] = subscores_df["Pillar"].map(
        {k: w for k, (_, w) in PILLAR_WEIGHTS.items()}
    )
    subscores_df["Pillar"] = subscores_df["Pillar"].map(
        {k: label for k, (label, _) in PILLAR_WEIGHTS.items()}
    )
    subscores_df["Weighted Contribution"] = (
        subscores_df["Score"] * subscores_df["Weight"]
    ).round(2)

    st.caption(
        "Left: each pillar's raw 0–100 score, showing which dimension a city is strong or weak in. "
        "Right: the same pillars multiplied by their weights — the points that actually build the composite."
    )

    b1, b2 = st.columns(2)

    with b1:
        st.markdown("##### Raw Pillar Scores (0–100)")
        raw_spec = (
            alt.Chart(subscores_df)
            .mark_bar()
            .encode(
                x=alt.X("city_name:N", title=None, sort=city_order, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Score:Q", title="Pillar Score (0–100)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Pillar:N", title="Pillar", sort=PILLAR_ORDER),
                xOffset=alt.XOffset("Pillar:N", sort=PILLAR_ORDER),
                tooltip=[
                    alt.Tooltip("city_name:N", title="City"),
                    alt.Tooltip("Pillar:N", title="Pillar"),
                    alt.Tooltip("Score:Q", title="Score", format=".1f"),
                    alt.Tooltip("Weight:Q", title="Weight", format=".0%"),
                ],
            )
            .properties(height=360)
        )
        render_chart(raw_spec, subscores_df, "city_name")

    with b2:
        st.markdown("##### Weighted Contribution to Composite (points)")
        contrib_spec = (
            alt.Chart(subscores_df)
            .mark_bar()
            .encode(
                x=alt.X("Weighted Contribution:Q", title="Composite Points", stack="zero"),
                y=alt.Y("city_name:N", title=None, sort=city_order),
                color=alt.Color("Pillar:N", title="Pillar", sort=PILLAR_ORDER),
                tooltip=[
                    alt.Tooltip("city_name:N", title="City"),
                    alt.Tooltip("Pillar:N", title="Pillar"),
                    alt.Tooltip("Score:Q", title="Raw Score", format=".1f"),
                    alt.Tooltip("Weight:Q", title="Weight", format=".0%"),
                    alt.Tooltip("Weighted Contribution:Q", title="Points", format=".2f"),
                ],
            )
            .properties(height=360)
        )
        render_chart(contrib_spec, subscores_df, "city_name")

    st.markdown("### Historical Composite Trend")
    trend_chart = (
        alt.Chart(df_ci)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Observation Date"),
            y=alt.Y("city_intelligence_score:Q", scale=alt.Scale(domain=[0, 100]), title="Index Score"),
            color=alt.Color("city_name:N", title="City"),
            tooltip=["city_name", "date", "city_intelligence_score", "avg_pm2_5", "transit_nodes"],
        )
        .properties(height=300)
    )
    render_chart(trend_chart, df_ci, "date")

    with st.expander("🔍 Traceability & Underlying Measure Data"):
        st.dataframe(df_ci, use_container_width=True)


# 2. Mobility & Urban Infrastructure Mart View
elif nav_page == "🚌 Mobility & Infrastructure":
    st.title("🚌 Mobility & Infrastructure Analytical Mart")
    st.markdown(
        """
        Synthesizes **OpenStreetMap (OSM) Overpass API** infrastructure density (bus stops, transit terminals,
        fuel distribution hubs, commercial centers) evaluated against open-meteo precipitation stressors.
        """
    )

    df_mob = query_df("""
        SELECT 
            m.city_id,
            c.city_name,
            c.country,
            c.population,
            m.date,
            m.transit_nodes_total,
            m.bus_stops,
            m.transit_stations,
            m.fuel_stations_total,
            m.commercial_nodes_total,
            m.daily_precip_mm,
            m.weather_stress_level,
            m.transit_density_sqkm,
            m.fuel_density_sqkm
        FROM (SELECT * FROM urbanpulse.mart_mobility_daily FINAL) m
        JOIN urbanpulse.dim_city c ON m.city_id = c.city_id
        ORDER BY m.date DESC, m.transit_nodes_total DESC
    """)

    # ReplacingMergeTree merges are asynchronous — collapse to one row per
    # (city, date) so column counts, metric cards and charts stay stable.
    df_mob = dedupe(df_mob, ["city_name", "date"])

    latest_date = df_mob["date"].max()
    latest_mob = (
        df_mob[df_mob["date"] == latest_date]
        .sort_values("transit_nodes_total", ascending=False)
        .reset_index(drop=True)
        .copy()
    )

    # Normalise the raw node counts against city population so the benchmark
    # compares accessibility per resident rather than rewarding sheer city size.
    latest_mob["transit_per_100k"] = (
        latest_mob["transit_nodes_total"] / (latest_mob["population"] / 100_000)
    ).round(2)
    latest_mob["fuel_per_100k"] = (
        latest_mob["fuel_stations_total"] / (latest_mob["population"] / 100_000)
    ).round(2)
    max_transit_density = pd.to_numeric(
        latest_mob["transit_density_sqkm"], errors="coerce"
    ).max()
    if pd.isna(max_transit_density) or max_transit_density <= 0:
        max_transit_density = 1.0
    max_transit_density = float(max_transit_density)

    st.subheader(f"Urban Catchment Density Benchmark — {latest_date}")
    st.caption(
        "Infrastructure nodes from the OSM Overpass API, counted inside a 15 km radius (706.86 km²) around "
        "each city centroid. This mart is a **spatial benchmark, not a time series**: OSM supplies a single "
        "infrastructure snapshot, so the page compares cities side by side rather than tracking mobility "
        "through time. Four charts follow — **G1–G2** spatial benchmarks, **G3–G4** environmental context."
    )

    if latest_mob.empty:
        st.warning("No mobility mart rows are available for the latest observation date.")
    else:
        infra_cols = st.columns(len(latest_mob))
        for idx, (_, row) in enumerate(latest_mob.iterrows()):
            with infra_cols[idx]:
                st.metric(
                    label=row["city_name"],
                    value=f"{row['transit_nodes_total']:,} transit nodes",
                    delta=f"{row['transit_density_sqkm']:.2f} nodes / km²",
                    delta_color="off",
                    help=(
                        f"Bus stops: {row['bus_stops']:,}\n\n"
                        f"Transit stations: {row['transit_stations']:,}\n\n"
                        f"Fuel stations: {row['fuel_stations_total']:,}\n\n"
                        f"Commercial nodes: {row['commercial_nodes_total']:,}\n\n"
                        f"Population: {row['population']:,}\n\n"
                        f"Accessibility: {row['transit_per_100k']:.1f} transit nodes per 100k residents"
                    ),
                )

    st.markdown("#### Catchment Benchmark Matrix")
    st.dataframe(
        latest_mob[[
            "city_name",
            "country",
            "population",
            "transit_nodes_total",
            "bus_stops",
            "transit_stations",
            "fuel_stations_total",
            "commercial_nodes_total",
            "transit_density_sqkm",
            "fuel_density_sqkm",
            "transit_per_100k",
            "fuel_per_100k",
            "daily_precip_mm",
            "weather_stress_level",
        ]].rename(columns={
            "city_name": "City",
            "country": "Country",
            "population": "Population",
            "transit_nodes_total": "Transit Nodes",
            "bus_stops": "Bus Stops",
            "transit_stations": "Transit Stations",
            "fuel_stations_total": "Fuel Stations",
            "commercial_nodes_total": "Commercial Nodes",
            "transit_density_sqkm": "Transit / km²",
            "fuel_density_sqkm": "Fuel / km²",
            "transit_per_100k": "Transit / 100k residents",
            "fuel_per_100k": "Fuel / 100k residents",
            "daily_precip_mm": "Daily Precip (mm)",
            "weather_stress_level": "Weather Stress",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Population": st.column_config.NumberColumn("Population", format="%d"),
            "Transit Nodes": st.column_config.NumberColumn("Transit Nodes", format="%d"),
            "Bus Stops": st.column_config.NumberColumn("Bus Stops", format="%d"),
            "Transit Stations": st.column_config.NumberColumn("Transit Stations", format="%d"),
            "Fuel Stations": st.column_config.NumberColumn("Fuel Stations", format="%d"),
            "Commercial Nodes": st.column_config.NumberColumn("Commercial Nodes", format="%d"),
            "Transit / km²": st.column_config.ProgressColumn(
                "Transit / km²", min_value=0.0, max_value=max_transit_density, format="%.3f"
            ),
            "Fuel / km²": st.column_config.NumberColumn("Fuel / km²", format="%.3f"),
            "Transit / 100k residents": st.column_config.NumberColumn(
                "Transit / 100k residents", format="%.1f"
            ),
            "Fuel / 100k residents": st.column_config.NumberColumn(
                "Fuel / 100k residents", format="%.1f"
            ),
            "Daily Precip (mm)": st.column_config.NumberColumn("Daily Precip (mm)", format="%.1f"),
        },
    )

    # Four deliberate visualisations (no headings without a chart):
    #   G1  Infrastructure density profile        (spatial, snapshot)
    #   G2  Accessibility per 100k residents      (spatial, snapshot)
    #   G3  Transit supply vs rainfall            (environmental context)
    #   G4  Daily rainfall timeline               (environmental context)
    st.markdown("### Mobility Visualisations")

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("#### G1 · Infrastructure Density Profile (nodes / km²)")
        density_df = latest_mob.melt(
            id_vars=["city_name"],
            value_vars=["transit_density_sqkm", "fuel_density_sqkm"],
            var_name="Metric",
            value_name="Nodes per km²",
        )
        density_df["Metric"] = density_df["Metric"].map({
            "transit_density_sqkm": "Transit nodes / km²",
            "fuel_density_sqkm": "Fuel stations / km²",
        })
        density_chart = (
            alt.Chart(density_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "city_name:N",
                    title=None,
                    sort=latest_mob["city_name"].tolist(),
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y("Nodes per km²:Q", title="Nodes per km²"),
                color=alt.Color(
                    "Metric:N",
                    title="Metric",
                    sort=["Transit nodes / km²", "Fuel stations / km²"],
                ),
                xOffset=alt.XOffset(
                    "Metric:N", sort=["Transit nodes / km²", "Fuel stations / km²"]
                ),
                tooltip=[
                    alt.Tooltip("city_name:N", title="City"),
                    alt.Tooltip("Metric:N", title="Metric"),
                    alt.Tooltip("Nodes per km²:Q", format=".3f"),
                ],
            )
            .properties(height=320)
        )
        render_chart(density_chart, density_df, "city_name")
        st.caption("Spatial supply per unit area. Higher = denser network inside the same catchment.")

    with g2:
        st.markdown("#### G2 · Accessibility per 100k Residents")
        access_df = latest_mob.melt(
            id_vars=["city_name"],
            value_vars=["transit_per_100k", "fuel_per_100k"],
            var_name="Metric",
            value_name="Nodes per 100k residents",
        )
        access_df["Metric"] = access_df["Metric"].map({
            "transit_per_100k": "Transit nodes / 100k",
            "fuel_per_100k": "Fuel stations / 100k",
        })
        access_chart = (
            alt.Chart(access_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "city_name:N",
                    title=None,
                    sort=latest_mob["city_name"].tolist(),
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y("Nodes per 100k residents:Q", title="Nodes per 100k residents"),
                color=alt.Color(
                    "Metric:N",
                    title="Metric",
                    sort=["Transit nodes / 100k", "Fuel stations / 100k"],
                ),
                xOffset=alt.XOffset(
                    "Metric:N", sort=["Transit nodes / 100k", "Fuel stations / 100k"]
                ),
                tooltip=[
                    alt.Tooltip("city_name:N", title="City"),
                    alt.Tooltip("Metric:N", title="Metric"),
                    alt.Tooltip("Nodes per 100k residents:Q", format=".2f"),
                    alt.Tooltip("population:Q", title="Population", format=","),
                ],
            )
            .properties(height=320)
        )
        render_chart(access_chart, access_df, "city_name")
        st.caption("Supply normalised by population — the fairer comparison across unequal city sizes.")

    st.markdown("### Environmental Context (the only time-varying measures)")
    st.caption(
        "OSM infrastructure counts are a single snapshot, so rainfall is the only genuinely varying signal "
        "in this mart. G3 and G4 therefore test the environment relationship without implying that supply "
        "responds to weather."
    )

    g3, g4 = st.columns(2)

    with g3:
        st.markdown("#### G3 · Transit Supply vs Rainfall (all 11 observed days)")
        stress_chart = (
            alt.Chart(df_mob)
            .mark_circle(size=70, opacity=0.7)
            .encode(
                x=alt.X("daily_precip_mm:Q", title="Daily Precipitation (mm)"),
                y=alt.Y("transit_nodes_total:Q", title="Transit Nodes"),
                color=alt.Color("city_name:N", title="City"),
                tooltip=[
                    alt.Tooltip("city_name:N", title="City"),
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("daily_precip_mm:Q", title="Precip (mm)", format=".1f"),
                    alt.Tooltip("transit_nodes_total:Q", title="Transit Nodes", format=","),
                    alt.Tooltip("weather_stress_level:N", title="Stress"),
                ],
            )
            .properties(height=320)
        )
        render_chart(stress_chart, df_mob, "date")
        st.caption(
            "Each city forms a flat band because supply is a fixed snapshot — rainfall does not move it. "
            "The chart makes that limitation visible instead of implying a correlation."
        )

    with g4:
        st.markdown("#### G4 · Daily Rainfall Timeline, 11 Days")
        rain_chart = (
            alt.Chart(df_mob)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title="Observation Date"),
                y=alt.Y("daily_precip_mm:Q", title="Daily Precipitation (mm)"),
                color=alt.Color("city_name:N", title="City"),
                tooltip=[
                    alt.Tooltip("city_name:N", title="City"),
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("daily_precip_mm:Q", title="Precip (mm)", format=".1f"),
                    alt.Tooltip("weather_stress_level:N", title="Stress Level"),
                ],
            )
            .properties(height=320)
        )
        render_chart(rain_chart, df_mob, "date")
        st.caption(
            "The environmental driver behind weather stress levels (Low < 5 mm, Moderate ≥ 5 mm, "
            "Severe ≥ 25 mm) that feeds the mobility and composite scores."
        )

    with st.expander("⚠️ Data Architecture Note: Static Infrastructure Supply vs. Dynamic Weather"):
        st.markdown(
            """
            **Baseline Architecture Note.** `fact_osm_infrastructure` holds **one baseline survey snapshot per
            city**, so `transit_nodes_total`, `bus_stops`, `fuel_stations_total` and
            `commercial_nodes_total` represent physical urban supply. The mobility mart joins
            that spatial supply baseline across active observation dates with daily precipitation to compute transit friction.

            **Operational Interpretation:** OpenStreetMap provides spatial infrastructure supply (G1, G2),
            while Open-Meteo provides the environmental weather stressors (G3, G4) that impact commute accessibility.
            Temporal demand modulation (e.g. hourly ridership counts or live road congestion) would require a GTFS-RT feed.
            """
        )

    st.markdown("### Mobility & Infrastructure Mart Raw Data")
    st.dataframe(df_mob, use_container_width=True)

# 3. Climate & Environmental Health Mart View
elif nav_page == "🌱 Climate & Environment":
    st.title("🌱 Climate & Environmental Health Mart")
    st.markdown(
        """
        Integrates hourly Open-Meteo temperature, humidity, and atmospheric pollutant observations (PM2.5, PM10, NO2)
        aggregated into daily climate matrices and compared against WHO clean-air exposure baselines.
        """
    )

    df_env = query_df("""
        SELECT 
            e.city_id,
            c.city_name,
            c.country,
            e.date,
            e.avg_temp_c,
            e.min_temp_c,
            e.max_temp_c,
            e.total_precip_mm,
            e.avg_humidity_pct,
            e.avg_pm2_5,
            e.max_pm2_5,
            e.avg_pm10,
            e.avg_no2,
            e.hours_pm25_unhealthy,
            e.aq_missingness_ratio
        FROM (SELECT * FROM urbanpulse.mart_environment_daily FINAL) e
        JOIN urbanpulse.dim_city c ON e.city_id = c.city_id
        ORDER BY e.date DESC, e.avg_pm2_5 DESC
    """)

    df_env = dedupe(df_env, ["city_name", "date"])

    cities = df_env["city_name"].unique().tolist()
    selected_city = st.selectbox("Select City for Environmental Deep-Dive:", ["All Cities"] + cities)

    filtered_env = df_env if selected_city == "All Cities" else df_env[df_env["city_name"] == selected_city]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Particulate Matter (PM2.5) Exposure vs WHO Threshold (15 µg/m³)")
        pm_chart = (
            alt.Chart(filtered_env)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("avg_pm2_5:Q", title="Average PM2.5 (µg/m³)"),
                color=alt.Color("city_name:N", title="City"),
                tooltip=["city_name", "date", "avg_pm2_5", "max_pm2_5", "hours_pm25_unhealthy"],
            )
            .properties(height=320)
        )
        render_chart(pm_chart, filtered_env, "date")

    with c2:
        st.markdown("#### Daily Temperature Dynamics (°C Min / Avg / Max)")
        temp_chart = (
            alt.Chart(filtered_env)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("avg_temp_c:Q", title="Avg Temperature (°C)"),
                color=alt.Color("city_name:N", title="City"),
                tooltip=["city_name", "date", "min_temp_c", "avg_temp_c", "max_temp_c"],
            )
            .properties(height=320)
        )
        render_chart(temp_chart, filtered_env, "date")

    st.markdown("### Environmental Mart Records & Missingness Auditing")
    st.dataframe(filtered_env, use_container_width=True)


# 4. Economic & FX Stability Mart View
elif nav_page == "💱 Economic & FX Stability":
    st.title("💱 Economic & Currency Stability Mart")
    st.markdown(
        """
        Monitors daily foreign exchange valuations (NGN and GHS relative to USD) and World Bank economic
        indicators. Computes daily percentage movements and currency volatility index.
        """
    )

    df_fx = query_df("""
        SELECT 
            f.date,
            f.city_id,
            f.country,
            toString(f.currency) AS currency,
            f.units_per_usd,
            f.prev_day_units_per_usd,
            f.day_pct_change,
            f.last_updated
        FROM (SELECT * FROM urbanpulse.mart_fx_daily FINAL) f
        ORDER BY f.date DESC, f.currency
    """)

    # The mart fans one FX rate out across every city in that currency zone.
    # Collapse to one logical row per (currency, date) before rendering, then take
    # the most recent observation per currency for the headline metric cards.
    df_fx = dedupe(df_fx, ["currency", "date"])

    if df_fx.empty:
        st.warning("No foreign-exchange mart rows are available yet.")
    else:
        latest_fx_date = df_fx["date"].max()
        fx_latest = (
            df_fx.sort_values("date")
            .groupby("currency", as_index=False)
            .last()
            .sort_values("currency")
            .reset_index(drop=True)
        )

        st.subheader(f"Current Foreign Exchange Rates — {latest_fx_date}")
        st.caption(
            "Quote convention: units of local currency per 1 USD (a rising number = local currency "
            "depreciating against the dollar). The 24h shift compares the latest daily rate against the "
            "previous observed business day; where no prior day exists yet, it is shown as a baseline."
        )

        fx_cols = st.columns(len(fx_latest))
        for idx, (_, row) in enumerate(fx_latest.iterrows()):
            pct = row["day_pct_change"]
            has_pct = pd.notna(pct)
            with fx_cols[idx]:
                st.metric(
                    label=f"{row['currency']} per 1 USD ({row['country']})",
                    value=f"{row['units_per_usd']:,.2f}",
                    delta=f"{pct:+.2f}% (24h shift)" if has_pct else "Baseline — no prior day",
                    delta_color="inverse" if has_pct else "off",
                    help=(
                        f"As of {row['date']}\n\n"
                        f"Previous observation: "
                        + (
                            f"{row['prev_day_units_per_usd']:,.2f} per USD"
                            if pd.notna(row["prev_day_units_per_usd"])
                            else "not yet available (first ingested day)"
                        )
                        + f"\n\nIngested at: {row['last_updated']}"
                    ),
                )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Exchange Rate Trajectory (local units per 1 USD)")
            fx_trend = (
                alt.Chart(df_fx)
                .mark_line(point=True)
                .encode(
                    x=alt.X("date:T", title="Observation Date"),
                    y=alt.Y("units_per_usd:Q", title="Units per 1 USD"),
                    color=alt.Color("currency:N", title="Currency"),
                    tooltip=[
                        alt.Tooltip("currency:N", title="Currency"),
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("units_per_usd:Q", title="Rate", format=",.4f"),
                    ],
                )
                .properties(height=320)
            )
            render_chart(fx_trend, df_fx, "date")

        with c2:
            st.markdown("#### Daily Volatility (24h % shift)")
            fx_vol = (
                alt.Chart(df_fx.dropna(subset=["day_pct_change"]))
                .mark_bar()
                .encode(
                    x=alt.X("date:T", title="Observation Date"),
                    y=alt.Y("day_pct_change:Q", title="24h Change (%)"),
                    color=alt.Color("currency:N", title="Currency"),
                    xOffset="currency:N",
                    tooltip=[
                        alt.Tooltip("currency:N", title="Currency"),
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("day_pct_change:Q", title="24h %", format="+.4f"),
                    ],
                )
                .properties(height=320)
            )
            render_chart(fx_vol, df_fx, "date")

        st.markdown("### Daily FX Mart Records")
        st.dataframe(
            df_fx.rename(columns={
                "date": "Date",
                "currency": "Currency",
                "country": "Country",
                "units_per_usd": "Units per USD",
                "prev_day_units_per_usd": "Previous Day",
                "day_pct_change": "24h Change (%)",
                "last_updated": "Ingested At",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### World Bank Macroeconomic Baseline Indicators")
    df_econ = query_df("""
        SELECT 
            country_code,
            indicator,
            year,
            value
        FROM urbanpulse.fact_economic_indicator FINAL
        ORDER BY country_code, indicator, year DESC
    """)
    df_econ = dedupe(df_econ, ["country_code", "indicator", "year"])

    st.dataframe(df_econ, use_container_width=True, hide_index=True)


# 5. Cross-Domain Interdependency Analytics
elif nav_page == "🔬 Cross-Domain Insights":
    st.title("🔬 Cross-Domain Analytical Interdependency")
    st.markdown(
        """
        Synthesizing multi-domain telemetry across climate, transportation infrastructure,
        macroeconomics, and media vibrancy to answer complex urban policy questions.
        """
    )

    t1, t2, t3, t4, t5 = st.tabs([
        "1. Weather & Transit Stress",
        "2. FX Devaluation & Mobility Cost",
        "3. Environmental Pressure Ranking",
        "4. Media Vibrancy vs. Mobility",
        "5. Urban Infrastructure per Population",
    ])

    with t1:
        st.subheader("Q1: How do weather conditions & rainfall relate to mobility stress?")
        st.markdown(
            "Evaluating rainfall severity against transit node accessibility. Cities categorized with elevated weather stress experience degraded transit accessibility."
        )
        df_q1 = query_df("""
            SELECT 
                c.city_name               AS city_name,
                m.date                    AS date,
                m.daily_precip_mm         AS daily_precip_mm,
                m.weather_stress_level    AS weather_stress_level,
                m.transit_nodes_total     AS transit_nodes_total,
                m.fuel_stations_total     AS fuel_stations_total
            FROM (SELECT * FROM urbanpulse.mart_mobility_daily FINAL) m
            JOIN urbanpulse.dim_city c ON m.city_id = c.city_id
            ORDER BY m.date DESC, m.daily_precip_mm DESC
        """)
        df_q1 = dedupe(df_q1, ["city_name", "date"])
        st.dataframe(df_q1, use_container_width=True, hide_index=True)

    with t2:
        st.subheader("Q2: How do currency fluctuations impact urban fuel & transport economics?")
        st.markdown(
            "Combining daily FX rate depreciation with urban fuel station density. High currency depreciation combined with low fuel availability signals supply risk."
        )
        df_q2 = query_df("""
            SELECT 
                ci.city_name            AS city_name,
                ci.date                 AS date,
                ci.units_per_usd        AS units_per_usd,
                fx.day_pct_change       AS fx_24h_pct_change,
                m.fuel_stations_total   AS fuel_stations_total,
                m.fuel_density_sqkm     AS fuel_density_sqkm
            FROM (SELECT * FROM urbanpulse.mart_city_intelligence_daily FINAL) ci
            JOIN (SELECT city_id, date, day_pct_change FROM urbanpulse.mart_fx_daily FINAL) fx
              ON ci.city_id = fx.city_id AND ci.date = fx.date
            JOIN (SELECT city_id, date, fuel_stations_total, fuel_density_sqkm FROM urbanpulse.mart_mobility_daily FINAL) m
              ON ci.city_id = m.city_id AND ci.date = m.date
            ORDER BY ci.date DESC, ci.city_name
        """)
        df_q2 = dedupe(df_q2, ["city_name", "date"])
        st.dataframe(df_q2, use_container_width=True, hide_index=True)

    with t3:
        st.subheader("Q3: Which cities experience the greatest environmental pressure?")
        st.markdown(
            "Synthesizing PM2.5 particulates, NO2 concentrations, and unhealthy air exposure hours."
        )
        df_q3 = query_df("""
            SELECT 
                c.city_name                 AS city_name,
                e.date                      AS date,
                e.avg_pm2_5                 AS avg_pm2_5,
                e.hours_pm25_unhealthy      AS hours_pm25_unhealthy,
                e.avg_no2                   AS avg_no2,
                ci.score_environment        AS score_environment
            FROM (SELECT * FROM urbanpulse.mart_environment_daily FINAL) e
            JOIN urbanpulse.dim_city c ON e.city_id = c.city_id
            JOIN (SELECT city_id, date, score_environment FROM urbanpulse.mart_city_intelligence_daily FINAL) ci
              ON e.city_id = ci.city_id AND e.date = ci.date
            ORDER BY e.avg_pm2_5 DESC
        """)
        df_q3 = dedupe(df_q3, ["city_name", "date"])
        st.dataframe(df_q3, use_container_width=True, hide_index=True)

    with t4:
        st.subheader("Q4: Does news intensity correlate with commercial & transit vitality?")
        st.markdown(
            "Cross-referencing GDELT news vibrancy shares with commercial nodes (banks, markets) and transit points."
        )
        df_q4 = query_df("""
            SELECT 
                ci.city_name                 AS city_name,
                ci.date                      AS date,
                ci.score_vibrancy            AS score_vibrancy,
                ci.news_intensity_pct        AS news_intensity_pct,
                m.commercial_nodes_total     AS commercial_nodes_total,
                m.transit_nodes_total        AS transit_nodes_total
            FROM (SELECT * FROM urbanpulse.mart_city_intelligence_daily FINAL) ci
            JOIN (SELECT city_id, date, commercial_nodes_total, transit_nodes_total FROM urbanpulse.mart_mobility_daily FINAL) m
              ON ci.city_id = m.city_id AND ci.date = m.date
            ORDER BY ci.news_intensity_pct DESC
        """)
        df_q4 = dedupe(df_q4, ["city_name", "date"])
        st.dataframe(df_q4, use_container_width=True, hide_index=True)

    with t5:
        st.subheader("Q5: Where are commercial and transit services concentrated relative to population?")
        st.markdown(
            "Synthesizes demographic figures from `dim_city` with conformed OpenStreetMap transit and commercial infrastructure."
        )
        df_q5 = query_df("""
            SELECT 
                c.city_name                                                          AS city_name,
                c.population                                                         AS population,
                m.transit_nodes_total                                                AS transit_nodes_total,
                m.commercial_nodes_total                                             AS commercial_nodes_total,
                round(m.transit_nodes_total / (c.population / 100000.0), 2)          AS transit_nodes_per_100k,
                round(m.commercial_nodes_total / (c.population / 100000.0), 2)       AS commercial_nodes_per_100k
            FROM urbanpulse.dim_city c
            JOIN (
                SELECT
                    city_id,
                    argMax(transit_nodes_total, date)    AS transit_nodes_total,
                    argMax(commercial_nodes_total, date) AS commercial_nodes_total
                FROM urbanpulse.mart_mobility_daily FINAL
                GROUP BY city_id
            ) m ON c.city_id = m.city_id
            ORDER BY transit_nodes_per_100k DESC
        """)
        df_q5 = dedupe(df_q5, ["city_name"])
        st.dataframe(df_q5, use_container_width=True, hide_index=True)


# 6. Quality, Provenance & Source Health Audit
elif nav_page == "🛡️ Quality & Provenance Audit":
    st.title("🛡️ Quality, Lineage & Warehouse Auditing")
    st.markdown(
        """
        Full transparent visibility into registered source metadata, table row counts,
        data quality constraints, and missingness metrics across the platform.
        """
    )

    st.subheader("0. Pipeline Freshness & Data Staleness")
    st.caption(
        "Every pipeline stage writes to `urbanpulse.ingestion_log`. The table below is the "
        "consumer-visible freshness contract: how old the newest trusted activity is, how old "
        "the newest error is, and which recent stages failed."
    )

    try:
        log_exists = query_df(
            "SHOW TABLES FROM urbanpulse LIKE 'ingestion_log'"
        )
        if log_exists.empty:
            st.warning(
                "Freshness unavailable: `urbanpulse.ingestion_log` does not exist yet. "
                "Run `python scripts/run_pipeline.py` once to seed observability."
            )
        else:
            freshness_df = query_df("""
                SELECT
                    maxIf(started_at, status IN ('success', 'duplicate')) AS latest_success_at,
                    maxIf(started_at, status = 'error')                  AS latest_error_at,
                    dateDiff('hour',
                        maxIf(started_at, status IN ('success', 'duplicate')),
                        now()
                    ) AS hours_since_success,
                    dateDiff('hour',
                        maxIf(started_at, status = 'error'),
                        now()
                    ) AS hours_since_error,
                    countIf(status = 'error' AND started_at > dateSub(hour, 36, now())) AS errors_36h,
                    countIf(status IN ('success', 'duplicate')
                        AND started_at > dateSub(hour, 36, now())) AS successes_36h
                FROM urbanpulse.ingestion_log
            """)
            fresh = freshness_df.iloc[0]
            latest_ok = fresh["latest_success_at"]
            hours_old = fresh["hours_since_success"]
            recent_errors = int(fresh["errors_36h"] or 0)

            if pd.isna(hours_old) or hours_old is None:
                st.error(
                    "🚨 No successful pipeline activity has ever been recorded. "
                    "All figures on this dashboard may be stale."
                )
            elif int(hours_old) > 36:
                st.error(
                    f"🚨 Warehouse is STALE — newest trusted activity was {latest_ok} "
                    f"({int(hours_old)}h ago, budget is 36h). Run the pipeline or check Airflow."
                )
            elif recent_errors > 0:
                st.warning(
                    f"⚠️ Warehouse is current (latest success {latest_ok}, {int(hours_old)}h ago) "
                    f"but {recent_errors} source/stage error(s) were recorded in the last 36h. "
                    "See the ingestion log below."
                )
            else:
                st.success(
                    f"✅ Warehouse is fresh — latest trusted activity {latest_ok} "
                    f"({int(hours_old)}h ago), no errors in the last 36h."
                )
    except Exception as exc:
        st.warning(f"Freshness check could not run against the warehouse: {exc}")

    st.subheader("1. Source Provenance & Registry (`dim_source`)")
    df_src = query_df("SELECT * FROM urbanpulse.dim_source")
    st.dataframe(df_src, use_container_width=True)

    st.subheader("2. Latest Ingestion Log Entries")
    st.caption(
        "Newest 50 rows of `urbanpulse.ingestion_log`: per-source pulls plus one row per "
        "pipeline stage. `duplicate` means checksum-identical to what the warehouse "
        "already holds — it proves the source responded, and counts as fresh."
    )
    try:
        log_tail = query_df("""
            SELECT run_id, source_id, city_id, started_at, finished_at,
                   status, rows_received, rows_loaded, rows_quarantined,
                   error_message
            FROM urbanpulse.ingestion_log
            ORDER BY started_at DESC
            LIMIT 50
        """)
        st.dataframe(log_tail, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.warning(f"Could not read urbanpulse.ingestion_log: {exc}")

    st.subheader("3. Warehouse Conformed Tables Row Counts")
    table_stats = []
    conformed_tables = [
        "raw.open_meteo_weather",
        "raw.open_meteo_air_quality",
        "raw.fx_rates",
        "raw.gdelt_news",
        "raw.world_bank",
        "raw.osm_infrastructure",
        "urbanpulse.dim_city",
        "urbanpulse.dim_source",
        "urbanpulse.fact_weather_hourly",
        "urbanpulse.fact_air_quality_hourly",
        "urbanpulse.fact_fx_daily",
        "urbanpulse.fact_news_intensity",
        "urbanpulse.fact_economic_indicator",
        "urbanpulse.fact_osm_infrastructure",
        "urbanpulse.mart_environment_daily",
        "urbanpulse.mart_fx_daily",
        "urbanpulse.mart_mobility_daily",
        "urbanpulse.mart_city_intelligence_daily",
    ]
    for tbl in conformed_tables:
        cnt = get_clickhouse_client().command(f"SELECT count() FROM {tbl}")
        table_stats.append({"Table Name": tbl, "Total Records": cnt})
    st.dataframe(pd.DataFrame(table_stats), use_container_width=True)

    st.subheader("4. Data Quality & Missingness Auditing")
    st.markdown(
        """
        - **Air Quality Missingness Ratio:** Tracked at daily grain in `mart_environment_daily`.
        - **Temperature Sanity Assertion:** Verified between -10°C and 60°C.
        - **FX Rates Assertion:** Strictly positive numbers with zero division protection.
        - **Composite Index Boundaries:** Mathematical enforcement between `0.0` and `100.0`.
        """
    )

