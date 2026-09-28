import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict

from ingestion.common.raw_store import RawStore

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "AfricaPulseDataPlatform/1.0 (academic capstone research; contact: data-engineering@africapulse.org)"


def query_city_infrastructure_counts(lat: float, lon: float, radius_m: int = 15000) -> Dict[str, int]:
    """
    Executes a single consolidated Overpass QL query returning counts for all transit
    and commercial amenities around the city center in one HTTP round-trip.
    """
    # Overpass allows unioning into counts
    query = f"""[out:json][timeout:25];
(
  node["highway"="bus_stop"](around:{radius_m}, {lat}, {lon});
  node["amenity"="bus_station"](around:{radius_m}, {lat}, {lon});
  node["amenity"="fuel"](around:{radius_m}, {lat}, {lon});
  node["amenity"="bank"](around:{radius_m}, {lat}, {lon});
  node["amenity"="marketplace"](around:{radius_m}, {lat}, {lon});
);
out tags;"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(OVERPASS_URL, data=data, headers=headers)

    counts = {
        "bus_stops": 0,
        "bus_stations": 0,
        "fuel_stations": 0,
        "banks": 0,
        "marketplaces": 0,
    }

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data_json = json.loads(resp.read().decode("utf-8"))
            for elem in data_json.get("elements", []):
                tags = elem.get("tags", {})
                if tags.get("highway") == "bus_stop":
                    counts["bus_stops"] += 1
                amenity = tags.get("amenity")
                if amenity == "bus_station":
                    counts["bus_stations"] += 1
                elif amenity == "fuel":
                    counts["fuel_stations"] += 1
                elif amenity == "bank":
                    counts["banks"] += 1
                elif amenity == "marketplace":
                    counts["marketplaces"] += 1
    except Exception as e:
        logger.warning(f"Overpass query failed for ({lat}, {lon}): {e}")

    return counts


def ingest_osm_infrastructure(store: RawStore, cities: list[dict]) -> list[dict]:
    """
    Extracts transit and commercial infrastructure node counts for all cities via Overpass API.
    Uses 1 single HTTP request per city.
    Saves immutable evidence to data/raw/osm_infrastructure/{city_id}/...
    """
    results = []
    radius_m = 15000  # 15km urban catchment area

    for city in cities:
        city_id = city["city_id"]
        city_name = city["name"]
        lat = city["lat"]
        lon = city["lon"]

        counts = query_city_infrastructure_counts(lat, lon, radius_m)

        bus_stops = counts["bus_stops"]
        stations = counts["bus_stations"]
        fuel = counts["fuel_stations"]
        banks = counts["banks"]
        markets = counts["marketplaces"]

        payload = {
            "city_id": city_id,
            "city_name": city_name,
            "radius_meters": radius_m,
            "center_lat": lat,
            "center_lon": lon,
            "bus_stops": bus_stops,
            "transit_stations": stations,
            "transit_nodes_total": bus_stops + stations,
            "fuel_stations_total": fuel,
            "commercial_banks": banks,
            "commercial_marketplaces": markets,
            "commercial_nodes_total": banks + markets,
        }

        path, digest, created = store.save(
            source="osm_infrastructure",
            city_id=city_id,
            payload=payload,
        )

        logger.info(
            f"OSM infrastructure [{city_name}]: transit={payload['transit_nodes_total']}, "
            f"fuel={fuel}, commercial={payload['commercial_nodes_total']} (created={created})"
        )

        results.append({
            "city_id": city_id,
            "path": str(path),
            "checksum": digest,
            "created": created,
            "payload": payload,
        })

    return results


def fetch_osm_city(client: Any, store: RawStore, city: dict) -> None:
    """
    Per-city fetcher adhering to (client, store, city) contract in run_ingestion.
    """
    city_id = city["city_id"]
    city_name = city["name"]
    lat = city["lat"]
    lon = city["lon"]
    radius_m = 15000

    counts = query_city_infrastructure_counts(lat, lon, radius_m)
    bus_stops = counts["bus_stops"]
    stations = counts["bus_stations"]
    fuel = counts["fuel_stations"]
    banks = counts["banks"]
    markets = counts["marketplaces"]

    payload = {
        "city_id": city_id,
        "city_name": city_name,
        "radius_meters": radius_m,
        "center_lat": lat,
        "center_lon": lon,
        "bus_stops": bus_stops,
        "transit_stations": stations,
        "transit_nodes_total": bus_stops + stations,
        "fuel_stations_total": fuel,
        "commercial_banks": banks,
        "commercial_marketplaces": markets,
        "commercial_nodes_total": banks + markets,
    }

    path, digest, created = store.save(
        source="osm_infrastructure",
        city_id=city_id,
        payload=payload,
    )

    logger.info(
        f"OSM infrastructure [{city_name}]: transit={payload['transit_nodes_total']}, "
        f"fuel={fuel}, commercial={payload['commercial_nodes_total']} (created={created})"
    )



