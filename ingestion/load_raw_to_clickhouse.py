"""Load raw evidence files into ClickHouse raw.* tables.

Bridges the hybrid raw layer: files remain the evidence of record; raw.* tables
make payloads queryable for SQL transformation.

Idempotent: raw tables are ReplacingMergeTree keyed on checksum, so re-running
this loader over the same files does not multiply rows.

Usage: python -m ingestion.load_raw_to_clickhouse
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load_raw")

SOURCE_TO_TABLE = {
    "open_meteo_weather": "raw.open_meteo_weather",
    "open_meteo_air_quality": "raw.open_meteo_air_quality",
    "fx_rates": "raw.fx_rates",
    "fx_frankfurter": "raw.fx_frankfurter",
    "gdelt_news": "raw.gdelt_news",
    "world_bank": "raw.world_bank",
    "osm_infrastructure": "raw.osm_infrastructure",
}


def main() -> None:
    load_dotenv()
    client = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )
    raw_dir = Path(os.environ.get("RAW_DATA_DIR", "./data/raw"))
    inserted = skipped = 0

    for source, table in SOURCE_TO_TABLE.items():
        for path in sorted((raw_dir / source).rglob("*.json")) if (raw_dir / source).exists() else []:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            checksum = envelope["checksum"]
            # Skip if this checksum is already loaded (cheap pre-check; the
            # ReplacingMergeTree is the real guarantee under concurrency).
            already = client.query(
                f"SELECT count() FROM {table} WHERE checksum = %(c)s",
                parameters={"c": checksum},
            ).result_rows[0][0]
            if already:
                skipped += 1
                continue
            client.insert(
                table,
                [[
                    checksum,
                    envelope["city_id"],
                    json.dumps(envelope["payload"], ensure_ascii=False),
                    datetime.fromisoformat(envelope["ingested_at_utc"]).replace(tzinfo=None),
                    str(path),
                ]],
                column_names=["checksum", "city_id", "payload", "ingested_at", "raw_file_path"],
            )
            inserted += 1
            log.info("loaded %s -> %s", path.name, table)

    log.info("Done. inserted=%d skipped(already present)=%d", inserted, skipped)


if __name__ == "__main__":
    main()
