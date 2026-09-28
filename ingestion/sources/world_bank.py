
import logging

from ingestion.common.http_client import HttpClient
from ingestion.common.raw_store import RawStore

log = logging.getLogger(__name__)

WB_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"

INDICATORS = {
    "SP.POP.TOTL": "population_total",
    "NY.GDP.PCAP.CD": "gdp_per_capita_usd",
    "SP.URB.TOTL.IN.ZS": "urban_population_pct",
}


def fetch_world_bank(client: HttpClient, store: RawStore, country_code: str) -> list[bool]:
    """Fetch all indicators for one country (e.g. 'NG'). Returns per-indicator flags."""
    results = []
    for indicator, _label in INDICATORS.items():
        payload = client.get_json(
            WB_URL.format(country=country_code, indicator=indicator),
            params={"format": "json", "per_page": 30, "mrv": 10},  # most recent 10 years
        )
        path, digest, created = store.save(
            "world_bank", f"{country_code.lower()}_{INDICATORS[indicator]}", payload
        )
        log.info("world_bank %s/%s: %s (%s)", country_code, indicator,
                 "new" if created else "duplicate", path)
        results.append(created)
    return results
