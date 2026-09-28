
CREATE DATABASE IF NOT EXISTS urbanpulse;

-- Conformed city dimension. Grain: one row per city.
CREATE TABLE IF NOT EXISTS urbanpulse.dim_city (
    city_id       String,
    city_name     String,
    country       String,
    country_code  FixedString(2),
    currency_code FixedString(3),
    latitude      Float64,
    longitude     Float64,
    timezone      String,
    population    UInt32,
    valid_from    DateTime DEFAULT toDateTime('2026-01-01 00:00:00'),
    is_current    UInt8 DEFAULT 1
) ENGINE = ReplacingMergeTree
ORDER BY (city_id, valid_from);

-- Seed city metadata
INSERT INTO urbanpulse.dim_city (city_id, city_name, country, country_code, currency_code, latitude, longitude, timezone, population)
VALUES
    ('ng_lagos', 'Lagos', 'Nigeria', 'NG', 'NGN', 6.5244, 3.3792, 'Africa/Lagos', 16000000),
    ('ng_abuja', 'Abuja', 'Nigeria', 'NG', 'NGN', 9.0765, 7.3986, 'Africa/Lagos', 3700000),
    ('ng_port_harcourt', 'Port Harcourt', 'Nigeria', 'NG', 'NGN', 4.8156, 7.0498, 'Africa/Lagos', 3300000),
    ('gh_accra', 'Accra', 'Ghana', 'GH', 'GHS', 5.6037, -0.1870, 'Africa/Accra', 2500000);

-- Source provenance dimension. Grain: one row per registered source (§12).
CREATE TABLE IF NOT EXISTS urbanpulse.dim_source (
    source_id     String,
    source_name   String,
    domain        LowCardinality(String),
    access_method String,
    terms_url     String,
    refresh_rate  String
) ENGINE = ReplacingMergeTree
ORDER BY source_id;

INSERT INTO urbanpulse.dim_source (source_id, source_name, domain, access_method, terms_url, refresh_rate)
VALUES
    ('open_meteo_weather', 'Open-Meteo Weather API', 'weather', 'api', 'https://open-meteo.com/en/terms', 'hourly'),
    ('open_meteo_air_quality', 'Open-Meteo CAMS Air Quality', 'air_quality', 'api', 'https://open-meteo.com/en/terms', 'hourly'),
    ('fx_rates', 'open.er-api.com USD Rates', 'fx', 'api', 'https://www.exchangerate-api.com/terms', 'daily'),
    ('fx_frankfurter', 'Frankfurter ECB Rates Cross-Check', 'fx', 'api', 'https://frankfurter.dev', 'daily'),
    ('gdelt_news', 'GDELT DOC 2.0 API', 'news', 'api', 'https://www.gdeltproject.org', '15min'),
    ('world_bank', 'World Bank Indicators API', 'economic', 'api', 'https://data.worldbank.org', 'annual'),
    ('osm_infrastructure', 'OpenStreetMap Overpass API', 'geospatial_mobility', 'api', 'https://www.openstreetmap.org/copyright', 'weekly'),
    ('tomtom_traffic', 'TomTom Traffic Flow API (Evaluated/Documented)', 'mobility', 'api', 'https://developer.tomtom.com/terms', 'ad_hoc');

