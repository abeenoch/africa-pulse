
CREATE DATABASE IF NOT EXISTS urbanpulse;


CREATE TABLE IF NOT EXISTS urbanpulse.mart_environment_daily (
    city_id                 String,
    date                    Date,
    avg_temp_c              Float32,
    min_temp_c              Float32,
    max_temp_c              Float32,
    total_precip_mm         Float32,
    avg_humidity_pct        Float32,
    avg_pm2_5               Nullable(Float32),
    max_pm2_5               Nullable(Float32),
    avg_pm10                Nullable(Float32),
    avg_no2                 Nullable(Float32),
    hours_pm25_unhealthy    UInt16,
    aq_missingness_ratio    Float32,
    weather_samples         UInt16,
    aq_samples              UInt16
) ENGINE = ReplacingMergeTree
ORDER BY (city_id, date);


CREATE TABLE IF NOT EXISTS urbanpulse.mart_fx_daily (
    date                    Date,
    city_id                 String,
    country                 String,
    currency                FixedString(3),
    units_per_usd           Float64,
    prev_day_units_per_usd  Nullable(Float64),
    day_pct_change          Nullable(Float64),
    last_updated            DateTime
) ENGINE = ReplacingMergeTree
ORDER BY (city_id, currency, date);


CREATE TABLE IF NOT EXISTS urbanpulse.mart_mobility_daily (
    city_id                 String,
    date                    Date,
    transit_nodes_total     UInt32,
    bus_stops               UInt32,
    transit_stations        UInt32,
    fuel_stations_total     UInt32,
    commercial_nodes_total  UInt32,
    daily_precip_mm         Float32,
    weather_stress_level    LowCardinality(String), -- Low, Moderate, Severe
    transit_density_sqkm    Float32,
    fuel_density_sqkm       Float32
) ENGINE = ReplacingMergeTree
ORDER BY (city_id, date);


CREATE TABLE IF NOT EXISTS urbanpulse.mart_city_intelligence_daily (
    city_id                 String,
    city_name               String,
    country                 String,
    date                    Date,
    city_intelligence_score Float32, -- Final composite index (0-100)
    score_environment       Float32, -- Sub-score (30% weight)
    score_economic          Float32, -- Sub-score (25% weight)
    score_mobility          Float32, -- Sub-score (25% weight)
    score_vibrancy          Float32, -- Sub-score (20% weight)
    avg_pm2_5               Nullable(Float32),
    units_per_usd           Nullable(Float64),
    transit_nodes           UInt32,
    news_intensity_pct      Float32,
    calculated_at           DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree
ORDER BY (city_id, date);

