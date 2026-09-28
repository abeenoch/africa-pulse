import logging

from ingestion.common.http_client import HttpClient
from ingestion.common.raw_store import RawStore

log = logging.getLogger(__name__)

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def _strip_volatile(payload: dict) -> dict:
    """Open-Meteo embeds 'generationtime_ms' (server render time) in every
    response. It changes on every call even when the data is identical, which
    would defeat checksum-based dedup. Remove it before checksumming — the
    observation content is what identifies the record."""
    payload.pop("generationtime_ms", None)
    return payload


def fetch_weather(client: HttpClient, store: RawStore, city: dict, past_days: int = 7, forecast_days: int = 3) -> bool:
    """Fetch hourly weather for one city. Returns True if new data was stored."""
    payload = client.get_json(
        WEATHER_URL,
        params={
            "latitude": city["lat"],
            "longitude": city["lon"],
            "hourly": "temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m",
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "UTC",  # normalize everything to UTC (brief §12)
        },
    )
    path, digest, created = store.save("open_meteo_weather", city["city_id"], _strip_volatile(payload))
    log.info("weather %s: %s (%s)", city["city_id"], "new" if created else "duplicate", path)
    return created


def fetch_air_quality(client: HttpClient, store: RawStore, city: dict, past_days: int = 7, forecast_days: int = 3) -> bool:
    payload = client.get_json(
        AQ_URL,
        params={
            "latitude": city["lat"],
            "longitude": city["lon"],
            "hourly": "pm10,pm2_5,nitrogen_dioxide,ozone",
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "UTC",
        },
    )
    path, digest, created = store.save("open_meteo_air_quality", city["city_id"], _strip_volatile(payload))
    log.info("air_quality %s: %s (%s)", city["city_id"], "new" if created else "duplicate", path)
    return created
