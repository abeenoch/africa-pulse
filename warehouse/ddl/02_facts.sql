
CREATE DATABASE IF NOT EXISTS urbanpulse;

-- 1. Weather Hourly Fact
CREATE TABLE IF NOT EXISTS urbanpulse.fact_weather_hourly (
    city_id             String,
    observed_at         DateTime,
    temperature_c       Nullable(Float32),
    precipitation_mm    Nullable(Float32),
    relative_humidity   Nullable(Float32),
    wind_speed_kmh      Nullable(Float32),
    source_id           String,
    raw_checksum        String,
    ingested_at         DateTime
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (city_id, observed_at);

-- 2. Air Quality Hourly Fact
CREATE TABLE IF NOT EXISTS urbanpulse.fact_air_quality_hourly (
    city_id             String,
    observed_at         DateTime,
    pm2_5_ugm3          Nullable(Float32),
    pm10_ugm3           Nullable(Float32),
    no2_ugm3            Nullable(Float32),
    o3_ugm3             Nullable(Float32),
    source_id           String,
    raw_checksum        String,
    ingested_at         DateTime
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (city_id, observed_at);

-- 3. FX Daily Fact
CREATE TABLE IF NOT EXISTS urbanpulse.fact_fx_daily (
    currency            FixedString(3),
    rate_date           Date,
    units_per_usd       Float64,
    source_id           String,
    raw_checksum        String,
    ingested_at         DateTime
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(rate_date)
ORDER BY (currency, rate_date);

-- 4. News Intensity Fact (GDELT)
CREATE TABLE IF NOT EXISTS urbanpulse.fact_news_intensity (
    city_id             String,
    observed_at         DateTime,
    mention_intensity   Float32,
    source_id           String,
    raw_checksum        String,
    ingested_at         DateTime
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (city_id, observed_at);

-- 5. Economic Indicators Fact (World Bank)
CREATE TABLE IF NOT EXISTS urbanpulse.fact_economic_indicator (
    country_code        FixedString(2),
    indicator           String,
    year                UInt16,
    value               Float64,
    source_id           String,
    raw_checksum        String,
    ingested_at         DateTime
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (country_code, indicator, year);

-- 6. Mobility & Commercial Infrastructure Fact (OpenStreetMap Overpass)
CREATE TABLE IF NOT EXISTS urbanpulse.fact_osm_infrastructure (
    city_id                 String,
    snapshot_date           Date,
    transit_nodes_total     UInt32,
    bus_stops               UInt32,
    transit_stations        UInt32,
    fuel_stations_total     UInt32,
    commercial_nodes_total  UInt32,
    commercial_banks        UInt32,
    commercial_marketplaces UInt32,
    source_id               String,
    raw_checksum            String,
    ingested_at             DateTime
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (city_id, snapshot_date);

-- Ingestion health / observability (§11: track source freshness).
CREATE TABLE IF NOT EXISTS urbanpulse.ingestion_log (
    run_id              UUID,
    source_id           String,
    city_id             Nullable(String),
    started_at          DateTime,
    finished_at         DateTime,
    status              LowCardinality(String),
    rows_received       UInt32,
    rows_loaded         UInt32,
    rows_quarantined    UInt32,
    raw_checksum        String,
    error_message       Nullable(String)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (source_id, started_at);

-- Quarantined observations preserved for investigation (§11).
CREATE TABLE IF NOT EXISTS urbanpulse.quarantine (
    quarantined_at      DateTime DEFAULT now(),
    source_id           String,
    city_id             Nullable(String),
    rule_violated       String,
    raw_record          String,
    raw_checksum        String
) ENGINE = MergeTree
PARTITION BY toYYYYMM(quarantined_at)
ORDER BY (source_id, quarantined_at);

