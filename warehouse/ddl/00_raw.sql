-- Hybrid raw evidence (inside ClickHouse). These are the ONLY tables the
-- native-SQL transformation path does not own — they are owned by the
-- loaders. Design: hybrid raw evidence —
--   * files on disk (data/raw/) = immutable evidence of record, survive DB loss
--   * these tables = queryable copy that the warehouse transforms read via JSONExtract
-- The checksum exists in both places and is the lineage join key.
-- ReplacingMergeTree() keyed on checksum: reloading the same raw file is a no-op
-- after merges — idempotent loads.
-- NOT a backfill store: every source is polled with a fixed window
-- (open-meteo past_days=7/forecast_days=3, GDELT timespan=24h, FX latest,
-- World Bank latest 10 years, OSM current snapshot). History grows only by
-- running the pipeline regularly; see decision log D7.
CREATE DATABASE IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.open_meteo_weather (
    checksum        String,              -- SHA-256 of payload; dedup + lineage key
    city_id         String,
    payload         String,              -- original JSON, unmodified
    ingested_at     DateTime,            -- when our platform received it 
    raw_file_path   String               -- pointer to evidence file on disk
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (city_id, checksum);

CREATE TABLE IF NOT EXISTS raw.open_meteo_air_quality (
    checksum        String,
    city_id         String,
    payload         String,
    ingested_at     DateTime,
    raw_file_path   String
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (city_id, checksum);

-- 'city_id' carries the scope of the observation: a real city_id, a country
-- indicator key (e.g. 'ng_population_total'), or 'global' (FX USD basket).
CREATE TABLE IF NOT EXISTS raw.fx_rates (
    checksum String, city_id String, payload String,
    ingested_at DateTime, raw_file_path String
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at) ORDER BY (city_id, checksum);

CREATE TABLE IF NOT EXISTS raw.fx_frankfurter (
    checksum String, city_id String, payload String,
    ingested_at DateTime, raw_file_path String
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at) ORDER BY (city_id, checksum);

-- raw.tomtom_traffic was declared here. TomTom was descoped (decision log D6:
-- verified zero traffic-flow coverage in Nigeria/Ghana) and this table never
-- held a row. Do not re-add it without re-running the coverage probe recorded
-- in docs/source_register.md.
CREATE TABLE IF NOT EXISTS raw.gdelt_news (
    checksum String, city_id String, payload String,
    ingested_at DateTime, raw_file_path String
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at) ORDER BY (city_id, checksum);

CREATE TABLE IF NOT EXISTS raw.world_bank (
    checksum String, city_id String, payload String,
    ingested_at DateTime, raw_file_path String
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at) ORDER BY (city_id, checksum);

CREATE TABLE IF NOT EXISTS raw.osm_infrastructure (
    checksum String, city_id String, payload String,
    ingested_at DateTime, raw_file_path String
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at) ORDER BY (city_id, checksum);


