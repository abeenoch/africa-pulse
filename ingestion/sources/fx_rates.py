
import logging

from ingestion.common.http_client import HttpClient
from ingestion.common.raw_store import RawStore

log = logging.getLogger(__name__)

ER_API_URL = "https://open.er-api.com/v6/latest/USD"
FRANKFURTER_URL = "https://api.frankfurter.app/latest"

# Fields in the er-api envelope that change per-call without new information
_VOLATILE = ("time_last_update_unix", "time_next_update_unix")


def _strip_volatile(payload: dict) -> dict:
    for k in _VOLATILE:
        payload.pop(k, None)
    return payload


def fetch_fx_usd(client: HttpClient, store: RawStore) -> bool:
    """USD-based rates for all currencies. Stored under city_id='global'."""
    payload = client.get_json(ER_API_URL)
    path, digest, created = store.save("fx_rates", "global", _strip_volatile(payload))
    log.info("fx USD base: %s (%s)", "new" if created else "duplicate", path)
    return created


def fetch_fx_frankfurter(client: HttpClient, store: RawStore) -> bool:
    """ECB reference rates (EUR base). Known gap: no NGN — documented, cross-check only."""
    payload = client.get_json(FRANKFURTER_URL, params={"from": "EUR", "to": "USD,GHS"})
    path, digest, created = store.save("fx_frankfurter", "global", payload)
    log.info("fx EUR base (ECB): %s (%s)", "new" if created else "duplicate", path)
    return created
