"""
Master Warehouse Transformation Pipeline (Pure ClickHouse SQL).
"""
import logging
import os
import re
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("warehouse_transform")


def get_client():
    load_dotenv()
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def run_ddl_file(client, file_path: Path):
    """Executes semi-colon separated statements in a SQL DDL file after stripping comments."""
    log.info(f"Applying DDL file: {file_path.name}")
    content = file_path.read_text(encoding="utf-8")
    content = re.sub(r"--.*", "", content)
    statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
    for stmt in statements:
        try:
            client.command(stmt)
        except Exception as e:
            log.error(f"Error executing statement in {file_path.name}: {e}\nStatement: {stmt[:120]}...")
            raise


def transform_facts(client):
    """Transforms raw JSON into clean conformed facts."""
    log.info("Transforming raw data into Conformed Facts...")

    log.info("  -> Loading urbanpulse.fact_weather_hourly")
    client.command("""
    INSERT INTO urbanpulse.fact_weather_hourly
    WITH expanded AS (
        SELECT
            city_id,
            checksum AS raw_checksum,
            ingested_at,
            arrayJoin(arrayZip(
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'time',                 'Array(String)'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'temperature_2m',       'Array(Nullable(Float64))'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'precipitation',        'Array(Nullable(Float64))'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'relative_humidity_2m', 'Array(Nullable(Float64))'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'wind_speed_10m',       'Array(Nullable(Float64))')
            )) AS rec
        FROM raw.open_meteo_weather FINAL
    )
    SELECT
        city_id,
        parseDateTimeBestEffort(rec.1, 'UTC') AS observed_at,
        toFloat32(rec.2)                      AS temperature_c,
        toFloat32(rec.3)                      AS precipitation_mm,
        toFloat32(rec.4)                      AS relative_humidity,
        toFloat32(rec.5)                      AS wind_speed_kmh,
        'open_meteo_weather'                  AS source_id,
        raw_checksum,
        ingested_at
    FROM expanded
    """)

    log.info("  -> Loading urbanpulse.fact_air_quality_hourly")
    client.command("""
    INSERT INTO urbanpulse.fact_air_quality_hourly
    WITH expanded AS (
        SELECT
            city_id,
            checksum AS raw_checksum,
            ingested_at,
            arrayJoin(arrayZip(
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'time',              'Array(String)'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'pm2_5',             'Array(Nullable(Float64))'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'pm10',              'Array(Nullable(Float64))'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'nitrogen_dioxide',  'Array(Nullable(Float64))'),
                JSONExtract(JSONExtractRaw(payload, 'hourly'), 'ozone',             'Array(Nullable(Float64))')
            )) AS rec
        FROM raw.open_meteo_air_quality FINAL
    )
    SELECT
        city_id,
        parseDateTimeBestEffort(rec.1, 'UTC') AS observed_at,
        toFloat32(rec.2)                      AS pm2_5_ugm3,
        toFloat32(rec.3)                      AS pm10_ugm3,
        toFloat32(rec.4)                      AS no2_ugm3,
        toFloat32(rec.5)                      AS o3_ugm3,
        'open_meteo_air_quality'              AS source_id,
        raw_checksum,
        ingested_at
    FROM expanded
    """)

    log.info("  -> Loading urbanpulse.fact_fx_daily")
    client.command("""
    INSERT INTO urbanpulse.fact_fx_daily
    WITH parsed AS (
        SELECT
            toDate(parseDateTimeBestEffort(JSONExtractString(payload, 'time_last_update_utc'), 'UTC')) AS rate_date,
            JSONExtractFloat(payload, 'rates', 'NGN') AS ngn_per_usd,
            JSONExtractFloat(payload, 'rates', 'GHS') AS ghs_per_usd,
            checksum AS raw_checksum,
            ingested_at
        FROM raw.fx_rates FINAL
        WHERE JSONExtractString(payload, 'result') = 'success'
    )
    SELECT 'NGN' AS currency, rate_date, ngn_per_usd AS units_per_usd, 'fx_rates' AS source_id, raw_checksum, ingested_at
    FROM parsed WHERE ngn_per_usd IS NOT NULL
    UNION ALL
    SELECT 'GHS' AS currency, rate_date, ghs_per_usd AS units_per_usd, 'fx_rates' AS source_id, raw_checksum, ingested_at
    FROM parsed WHERE ghs_per_usd IS NOT NULL
    """)

    log.info("  -> Loading urbanpulse.fact_news_intensity")
    client.command("""
    INSERT INTO urbanpulse.fact_news_intensity
    WITH expanded AS (
        SELECT
            city_id,
            checksum AS raw_checksum,
            ingested_at,
            arrayJoin(
                JSONExtract(payload, 'timeline', 1, 'data',
                            'Array(Tuple(date String, value Float64))')
            ) AS rec
        FROM raw.gdelt_news FINAL
    )
    SELECT
        city_id,
        parseDateTimeBestEffort(rec.date, 'UTC') AS observed_at,
        toFloat32(rec.value)                     AS mention_intensity,
        'gdelt_news'                             AS source_id,
        raw_checksum,
        ingested_at
    FROM expanded
    """)

    log.info("  -> Loading urbanpulse.fact_economic_indicator")
    client.command("""
    INSERT INTO urbanpulse.fact_economic_indicator
    WITH expanded AS (
        SELECT
            city_id,
            checksum AS raw_checksum,
            ingested_at,
            arrayJoin(
                JSONExtract(payload, 2, 'Array(Tuple(
                    indicator Tuple(id String),
                    country   Tuple(id String),
                    date      String,
                    value     Nullable(Float64)))')
            ) AS rec
        FROM raw.world_bank FINAL
    )
    SELECT
        lower(rec.country.id) AS country_code,
        rec.indicator.id      AS indicator,
        toUInt16(rec.date)    AS year,
        rec.value             AS value,
        'world_bank'          AS source_id,
        raw_checksum,
        ingested_at
    FROM expanded
    WHERE rec.value IS NOT NULL
    """)

    log.info("  -> Loading urbanpulse.fact_osm_infrastructure")
    client.command("""
    INSERT INTO urbanpulse.fact_osm_infrastructure
    SELECT
        city_id,
        toDate(ingested_at)                                          AS snapshot_date,
        toUInt32(JSONExtractUInt(payload, 'transit_nodes_total'))    AS transit_nodes_total,
        toUInt32(JSONExtractUInt(payload, 'bus_stops'))              AS bus_stops,
        toUInt32(JSONExtractUInt(payload, 'transit_stations'))       AS transit_stations,
        toUInt32(JSONExtractUInt(payload, 'fuel_stations_total'))    AS fuel_stations_total,
        toUInt32(JSONExtractUInt(payload, 'commercial_nodes_total')) AS commercial_nodes_total,
        toUInt32(JSONExtractUInt(payload, 'commercial_banks'))       AS commercial_banks,
        toUInt32(JSONExtractUInt(payload, 'commercial_marketplaces')) AS commercial_marketplaces,
        'osm_infrastructure'                                         AS source_id,
        checksum                                                     AS raw_checksum,
        ingested_at
    FROM raw.osm_infrastructure FINAL
    """)

def transform_marts(client):
    """
    Builds the 4 analytical data marts:
    1. Climate & Environment
    2. Economic / FX
    3. Mobility & Infrastructure
    4. City Intelligence Composite Score (0-100)
    """
    log.info("Transforming conformed facts into Analytical Marts...")

    log.info("  -> Refreshing urbanpulse.mart_environment_daily")
    client.command("TRUNCATE TABLE urbanpulse.mart_environment_daily")
    client.command("""
    INSERT INTO urbanpulse.mart_environment_daily
    WITH daily_weather AS (
        SELECT
            city_id,
            toDate(observed_at) AS date,
            round(avg(temperature_c), 2)     AS avg_temp_c,
            min(temperature_c)              AS min_temp_c,
            max(temperature_c)              AS max_temp_c,
            round(sum(precipitation_mm), 2) AS total_precip_mm,
            round(avg(relative_humidity), 2) AS avg_humidity_pct,
            count()                         AS weather_samples
        FROM urbanpulse.fact_weather_hourly FINAL
        GROUP BY city_id, date
    ),
    daily_aq AS (
        SELECT
            city_id,
            toDate(observed_at) AS date,
            round(avg(pm2_5_ugm3), 2)        AS avg_pm2_5,
            max(pm2_5_ugm3)                 AS max_pm2_5,
            round(avg(pm10_ugm3), 2)         AS avg_pm10,
            round(avg(no2_ugm3), 2)          AS avg_no2,
            countIf(pm2_5_ugm3 > 35.4)       AS hours_pm25_unhealthy,
            round(countIf(pm2_5_ugm3 IS NULL) / count(), 4) AS aq_missingness_ratio,
            count()                         AS aq_samples
        FROM urbanpulse.fact_air_quality_hourly FINAL
        GROUP BY city_id, date
    )
    SELECT
        w.city_id,
        w.date,
        w.avg_temp_c,
        w.min_temp_c,
        w.max_temp_c,
        w.total_precip_mm,
        w.avg_humidity_pct,
        a.avg_pm2_5,
        a.max_pm2_5,
        a.avg_pm10,
        a.avg_no2,
        coalesce(a.hours_pm25_unhealthy, 0) AS hours_pm25_unhealthy,
        coalesce(a.aq_missingness_ratio, 1.0) AS aq_missingness_ratio,
        w.weather_samples,
        coalesce(a.aq_samples, 0) AS aq_samples
    FROM daily_weather w
    LEFT JOIN daily_aq a ON w.city_id = a.city_id AND w.date = a.date
    """)

    log.info("  -> Refreshing urbanpulse.mart_fx_daily")
    client.command("TRUNCATE TABLE urbanpulse.mart_fx_daily")
    client.command("""
    INSERT INTO urbanpulse.mart_fx_daily
    WITH lagged AS (
        SELECT
            rate_date AS date,
            currency,
            units_per_usd,
            lagInFrame(toNullable(units_per_usd)) OVER (
                PARTITION BY currency ORDER BY rate_date
            ) AS prev_day_units_per_usd,
            ingested_at
        FROM urbanpulse.fact_fx_daily FINAL
    )
    SELECT
        l.date,
        c.city_id,
        c.country,
        l.currency,
        l.units_per_usd,
        l.prev_day_units_per_usd,
        CASE
            WHEN l.prev_day_units_per_usd IS NOT NULL AND l.prev_day_units_per_usd > 0
            THEN round(((l.units_per_usd - l.prev_day_units_per_usd) / l.prev_day_units_per_usd) * 100.0, 4)
            ELSE NULL
        END AS day_pct_change,
        l.ingested_at AS last_updated
    FROM lagged l
    JOIN urbanpulse.dim_city c ON c.currency_code = l.currency
    """)

    log.info("  -> Refreshing urbanpulse.mart_mobility_daily")
    client.command("TRUNCATE TABLE urbanpulse.mart_mobility_daily")
    client.command("""
    INSERT INTO urbanpulse.mart_mobility_daily
    WITH latest_infra AS (
        SELECT
            city_id,
            argMax(transit_nodes_total, snapshot_date)     AS transit_nodes_total,
            argMax(bus_stops, snapshot_date)               AS bus_stops,
            argMax(transit_stations, snapshot_date)        AS transit_stations,
            argMax(fuel_stations_total, snapshot_date)     AS fuel_stations_total,
            argMax(commercial_nodes_total, snapshot_date)  AS commercial_nodes_total
        FROM urbanpulse.fact_osm_infrastructure FINAL
        GROUP BY city_id
    ),
    weather_stress AS (
        SELECT
            city_id,
            date,
            total_precip_mm,
            CASE
                WHEN total_precip_mm >= 25.0 THEN 'Severe'
                WHEN total_precip_mm >= 5.0  THEN 'Moderate'
                ELSE 'Low'
            END AS weather_stress_level
        FROM urbanpulse.mart_environment_daily FINAL
    )
    SELECT
        w.city_id,
        w.date,
        coalesce(i.transit_nodes_total, 0)    AS transit_nodes_total,
        coalesce(i.bus_stops, 0)              AS bus_stops,
        coalesce(i.transit_stations, 0)       AS transit_stations,
        coalesce(i.fuel_stations_total, 0)    AS fuel_stations_total,
        coalesce(i.commercial_nodes_total, 0) AS commercial_nodes_total,
        w.total_precip_mm                     AS daily_precip_mm,
        w.weather_stress_level,
        round(coalesce(i.transit_nodes_total, 0) / 706.86, 4) AS transit_density_sqkm,
        round(coalesce(i.fuel_stations_total, 0) / 706.86, 4) AS fuel_density_sqkm
    FROM weather_stress w
    LEFT JOIN latest_infra i ON w.city_id = i.city_id
    """)

    log.info("  -> Refreshing urbanpulse.mart_city_intelligence_daily")
    client.command("TRUNCATE TABLE urbanpulse.mart_city_intelligence_daily")
    client.command("""
    INSERT INTO urbanpulse.mart_city_intelligence_daily
    WITH env AS (
        SELECT
            city_id,
            date,
            avg_pm2_5,
            greatest(0.0, least(100.0, toFloat32(100.0 - coalesce(avg_pm2_5, 25.0)))) AS score_env
        FROM urbanpulse.mart_environment_daily FINAL
    ),
    fx AS (
        SELECT
            city_id,
            date,
            units_per_usd,
            day_pct_change,
            toNullable(greatest(0.0, least(100.0, toFloat32(100.0 - abs(coalesce(day_pct_change, 0.0)) * 10.0)))) AS score_econ
        FROM urbanpulse.mart_fx_daily FINAL
    ),
    mob AS (
        SELECT
            city_id,
            date,
            transit_nodes_total,
            toNullable(greatest(0.0, least(100.0, toFloat32(transit_nodes_total / 10.0)))) AS score_mob
        FROM urbanpulse.mart_mobility_daily FINAL
    ),
    news AS (
        SELECT
            city_id,
            toDate(observed_at) AS date,
            round(avg(mention_intensity), 4) AS news_intensity_pct,
            toNullable(greatest(0.0, least(100.0, toFloat32(avg(mention_intensity) * 200.0)))) AS score_vib
        FROM urbanpulse.fact_news_intensity FINAL
        GROUP BY city_id, date
    )
    SELECT
        c.city_id,
        c.city_name,
        c.country,
        e.date,
        round(
            (0.30 * e.score_env) +
            (0.25 * coalesce(f.score_econ, 80.0)) +
            (0.25 * coalesce(m.score_mob, 50.0)) +
            (0.20 * coalesce(n.score_vib, 50.0)),
            2
        ) AS city_intelligence_score,
        round(e.score_env, 2) AS score_environment,
        round(coalesce(f.score_econ, 80.0), 2) AS score_economic,
        round(coalesce(m.score_mob, 50.0), 2) AS score_mobility,
        round(coalesce(n.score_vib, 50.0), 2) AS score_vibrancy,
        e.avg_pm2_5,
        toNullable(f.units_per_usd) AS units_per_usd,
        coalesce(m.transit_nodes_total, 0) AS transit_nodes,
        coalesce(n.news_intensity_pct, 0.0) AS news_intensity_pct,
        now() AS calculated_at
    FROM env e
    JOIN urbanpulse.dim_city c ON e.city_id = c.city_id
    LEFT JOIN fx f   ON e.city_id = f.city_id AND e.date = f.date
    LEFT JOIN mob m  ON e.city_id = m.city_id AND e.date = m.date
    LEFT JOIN news n ON e.city_id = n.city_id AND e.date = n.date
    """)


def main():
    client = get_client()
    ddl_dir = Path("warehouse/ddl")
    
    run_ddl_file(client, ddl_dir / "00_raw.sql")
    run_ddl_file(client, ddl_dir / "01_dimensions.sql")
    run_ddl_file(client, ddl_dir / "02_facts.sql")
    run_ddl_file(client, ddl_dir / "03_marts.sql")

    transform_facts(client)
    transform_marts(client)

    log.info("ALL TRANSFORMATIONS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()

