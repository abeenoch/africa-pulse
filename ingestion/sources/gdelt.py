
import logging
import time

from ingestion.common.http_client import HttpClient
from ingestion.common.raw_store import RawStore

log = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT's DOC API enforces a strict per-IP rate limit (empirically ~1 req/6s;
# retry backoff alone still hit 429s). Pace requests proactively - source
# constraint respected, not fought (brief section 13).
_MIN_INTERVAL_S = 7.0
_last_call = 0.0


def _pace() -> None:
    global _last_call
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        log.info("gdelt pacing: sleeping %.1fs to respect rate limit", wait)
        time.sleep(wait)
    _last_call = time.monotonic()


def fetch_news_intensity(client: HttpClient, store: RawStore, city: dict) -> bool:
    """Fetch 24h news-volume timeline for one city. True if new data stored."""
    _pace()
    payload = client.get_json(
        GDELT_URL,
        params={
            "query": '"' + city["name"] + '"',
            "mode": "timelinevolinfo",
            "format": "json",
            "timespan": "1d",
            "timelinesmooth": 0,
        },
    )
    path, digest, created = store.save("gdelt_news", city["city_id"], payload)
    log.info("gdelt %s: %s (%s)", city["city_id"], "new" if created else "duplicate", path)
    return created
