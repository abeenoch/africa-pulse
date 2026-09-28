"""
Africa Pulse — Master Pipeline Orchestrator .

Single, automated, production entrypoint executing the complete data platform lifecycle:
  Stage 1: Multi-source acquisition (weather, air quality, FX, GDELT news, World Bank, OSM Overpass)
  Stage 2: Immutable raw evidence synchronization into ClickHouse raw.* tables
  Stage 3: Conformed warehouse transformation into dimensional facts and serving marts
  Stage 4: Automated Data Quality & Mathematical Assertion test suite

Usage:
  python scripts/run_pipeline.py
  python scripts/run_pipeline.py --skip-ingestion  # runs load, transform, and tests only
"""

import argparse
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path so imports work seamlessly from any working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion import run_ingestion
from ingestion import load_raw_to_clickhouse
from ingestion.common.observability import record_stage_row
from warehouse import transform
from tests import test_data_quality

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("master_pipeline")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_pipeline(skip_ingestion: bool = False) -> int:
    start_total = time.time()
    run_id = str(uuid.uuid4())
    log.info("=" * 70)
    log.info("STARTING AFRICA PULSE MASTER DATA PIPELINE")
    log.info("Pipeline run id: %s", run_id)
    log.info("=" * 70)

   
    if not skip_ingestion:
        log.info("\n>>> STAGE 1: Acquiring Multi-Source Data into Raw Evidence Store...")
        t0 = time.time()
        try:
            status = run_ingestion.main()
            if status != 0:
                log.warning("Stage 1 completed with non-zero status code: %d", status)
        except Exception as exc:
            log.error("Stage 1 failed with critical exception: %s", exc)
            return 1
        log.info("Stage 1 complete in %.2f seconds.", time.time() - t0)
    else:
        log.info("\n>>> STAGE 1: Skipping Ingestion (--skip-ingestion flag supplied)")

   
    log.info("\n>>> STAGE 2: Synchronizing Raw Payloads into ClickHouse raw.* Tables...")
    stage_start = _utcnow()
    t0 = time.time()
    try:
        load_raw_to_clickhouse.main()
    except Exception as exc:
        log.error("Stage 2 failed: %s", exc)
        record_stage_row("raw_sync", "error", stage_start, _utcnow(), str(exc), run_id)
        return 1
    record_stage_row("raw_sync", "success", stage_start, _utcnow(), None, run_id)
    log.info("Stage 2 complete in %.2f seconds.", time.time() - t0)

    
    log.info("\n>>> STAGE 3: Transforming Warehouse Facts & Analytical Marts...")
    stage_start = _utcnow()
    t0 = time.time()
    try:
        transform.main()
    except Exception as exc:
        log.error("Stage 3 failed: %s", exc)
        record_stage_row("transform", "error", stage_start, _utcnow(), str(exc), run_id)
        return 1
    record_stage_row("transform", "success", stage_start, _utcnow(), None, run_id)
    log.info("Stage 3 complete in %.2f seconds.", time.time() - t0)

    
    log.info("\n>>> STAGE 4: Running Automated Data Quality & Boundary Tests...")
    stage_start = _utcnow()
    t0 = time.time()
    try:
        client = test_data_quality.get_client()
        test_data_quality.test_dimensions_loaded(client)
        test_data_quality.test_conformed_facts_row_counts(client)
        test_data_quality.test_fact_data_ranges_and_constraints(client)
        test_data_quality.test_marts_populated_and_valid(client)
        test_data_quality.test_composite_index_mathematical_bounds(client)
        # NOTE: test_ingestion_log_fresh is deliberately not called here — this
        # run has just written its own stage rows, so asserting freshness in
        # process would be circular. It runs in the standalone suite below
        # (and in Airflow's quality_gates task), where it proves an *earlier*
        # scheduled run actually happened.
    except AssertionError as ae:
        log.error("DATA QUALITY ASSERTION VIOLATION: %s", ae)
        record_stage_row("quality_tests", "error", stage_start, _utcnow(), str(ae), run_id)
        return 2
    except Exception as exc:
        log.error("Quality test execution failed: %s", exc)
        record_stage_row("quality_tests", "error", stage_start, _utcnow(), str(exc), run_id)
        return 2
    record_stage_row("quality_tests", "success", stage_start, _utcnow(), None, run_id)
    log.info("Stage 4 complete: All quality assertions passed in %.2f seconds.", time.time() - t0)

    total_time = time.time() - start_total
    log.info("\n" + "=" * 70)
    log.info("AFRICA PULSE MASTER PIPELINE COMPLETED SUCCESSFULLY (%.2fs)", total_time)
    log.info("=" * 70)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Africa Pulse Master Pipeline")
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip API/live acquisition and run warehouse sync, transform, and tests on existing data.",
    )
    args = parser.parse_args()
    sys.exit(run_pipeline(skip_ingestion=args.skip_ingestion))


if __name__ == "__main__":
    main()
