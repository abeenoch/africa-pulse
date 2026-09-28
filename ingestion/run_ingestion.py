
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import yaml
from dotenv import load_dotenv

from ingestion.common.http_client import HttpClient
from ingestion.common.observability import record_ingestion_run
from ingestion.common.raw_store import RawStore
from ingestion.sources import fx_rates, gdelt, open_meteo, osm_overpass, world_bank

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_ingestion")

CITY_FETCHERS = [
    ("open_meteo_weather", open_meteo.fetch_weather),
    ("open_meteo_air_quality", open_meteo.fetch_air_quality),
    ("gdelt_news", gdelt.fetch_news_intensity),
    ("osm_infrastructure", osm_overpass.fetch_osm_city),
]
GLOBAL_FETCHERS = [
    ("fx_rates", fx_rates.fetch_fx_usd),
    ("fx_frankfurter", fx_rates.fetch_fx_frankfurter),
]
COUNTRY_FETCHERS = [
    ("world_bank", world_bank.fetch_world_bank),
]


def _run_fetcher(fetcher, client, store, *args, source_label, scope_label, outcomes):
    """Run one fetcher, translate its boolean/None/list result into an ingestion_log row."""
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    outcome = {
        "source_id": source_label,
        "city_id": scope_label,
        "started_at": started,
        "finished_at": started,
        "status": "error",
        "rows_received": 0,
        "rows_loaded": 0,
        "rows_quarantined": 0,
        "raw_checksum": "",
        "error_message": None,
    }
    try:
        created = fetcher(client, store, *args)
        flags = created if isinstance(created, list) else [created]
        outcome["rows_received"] = len(flags)
        outcome["rows_loaded"] = sum(1 for flag in flags if flag)
        outcome["status"] = (
            "success" if any(flags)
            else ("duplicate" if flags else "success")
        )
    except Exception as exc:
        outcome["error_message"] = f"{type(exc).__name__}: {exc}"[:2000]
        log.error("SOURCE UNAVAILABLE: %s%s - %s", source_label,
                  f" / {scope_label}" if scope_label else "", exc)
    outcome["finished_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    outcomes.append(outcome)
    return outcome["status"]


def main() -> int:
    load_dotenv()
    cities = yaml.safe_load(Path("config/cities.yaml").read_text(encoding="utf-8"))["cities"]
    client = HttpClient()
    store = RawStore(os.environ.get("RAW_DATA_DIR", "./data/raw"))
    outcomes = []

    failures = 0

    # Global sources (once per run)
    for source_name, fetcher in GLOBAL_FETCHERS:
        status = _run_fetcher(fetcher, client, store,
                              source_label=source_name, scope_label=None, outcomes=outcomes)
        failures += status == "error"

    # Country sources (once per unique country)
    countries = sorted({c["country_code"] for c in cities})
    for country in countries:
        for source_name, fetcher in COUNTRY_FETCHERS:
            status = _run_fetcher(fetcher, client, store, country,
                                  source_label=source_name, scope_label=country,
                                  outcomes=outcomes)
            failures += status == "error"

    # City sources
    for city in cities:
        for source_name, fetcher in CITY_FETCHERS:
            status = _run_fetcher(fetcher, client, store, city,
                                  source_label=source_name,
                                  scope_label=city["city_id"], outcomes=outcomes)
            failures += status == "error"

    record_ingestion_run(outcomes)
    log.info("Run complete. %d source outcomes, %d failures recorded.", len(outcomes), failures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
