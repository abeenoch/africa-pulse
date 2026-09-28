
import logging
import os
import uuid
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def _now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_client():
    """Import ClickHouse lazily so ingestion still works without warehouse deps."""
    import clickhouse_connect
    from dotenv import load_dotenv

    load_dotenv()
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def record_ingestion_run(outcomes, run_id: str | None = None):
    """Persist one ingestion_log row per fetched source/city/country/global batch.

    `outcomes` is a list of dicts with keys: source_id, city_id (or None),
    started_at, finished_at, status ('success'/'duplicate'/'error'),
    rows_received, rows_loaded, rows_quarantined, raw_checksum, error_message.
    """
    run_id = run_id or str(uuid.uuid4())
    try:
        client = _get_client()
    except Exception as exc:  # observability never breaks ingestion
        log.warning("ingestion_log unavailable, outcomes kept in stdout only: %s", exc)
        return run_id

    rows = [
        [
            run_id,
            o["source_id"],
            o.get("city_id"),
            o["started_at"],
            o["finished_at"],
            o["status"],
            int(o.get("rows_received", 0)),
            int(o.get("rows_loaded", 0)),
            int(o.get("rows_quarantined", 0)),
            o.get("raw_checksum", ""),
            o.get("error_message"),
        ]
        for o in outcomes
    ]
    try:
        client.insert(
            "urbanpulse.ingestion_log",
            rows,
            column_names=[
                "run_id", "source_id", "city_id", "started_at", "finished_at",
                "status", "rows_received", "rows_loaded", "rows_quarantined",
                "raw_checksum", "error_message",
            ],
        )
        log.info("ingestion_log: recorded %d outcome rows (run %s)", len(rows), run_id[:8])
    except Exception as exc:
        log.warning("failed to persist ingestion_log outcomes: %s", exc)
    return run_id


def record_stage_row(stage, status, started_at, finished_at, error_message=None, run_id=None):
    """Persist one pipeline-stage audit row (stages 2/3/4, brief §5)."""
    record_ingestion_run(
        [{
            "source_id": f"stage:{stage}",
            "city_id": None,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "rows_received": 0,
            "rows_loaded": 0,
            "rows_quarantined": 0,
            "raw_checksum": "",
            "error_message": error_message,
        }],
        run_id=run_id,
    )
