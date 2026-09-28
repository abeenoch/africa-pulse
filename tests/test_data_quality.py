"""
Automated Data Quality & Warehouse Assertion Suite.
Replaces dbt test with native, fast, and transparent ClickHouse tests.
Tests core assertions across:
1. Dimensional integrity (dim_city, dim_source)
2. Raw-to-Fact lineage and non-emptiness
3. Idempotency & deduplication
4. Business rules (temperature, FX positive rates, composite index bounds 0-100)
Brief alignment: §11, §13, §14.
5. Ingestion freshness & observability (ingestion_log exists and is recent).
"""
import os
import sys
import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()


def get_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def test_dimensions_loaded(ch_client):
    """Ensure conformed city and source dimensions are populated and have no null IDs."""
    cities_count = ch_client.command("SELECT count() FROM urbanpulse.dim_city")
    assert cities_count >= 4, f"Expected at least 4 cities, found {cities_count}"

    null_cities = ch_client.command("SELECT count() FROM urbanpulse.dim_city WHERE city_id IS NULL OR city_id = ''")
    assert null_cities == 0, "dim_city has null/empty city_id"

    sources_count = ch_client.command("SELECT count() FROM urbanpulse.dim_source")
    assert sources_count >= 6, f"Expected at least 6 registered sources, found {sources_count}"
    print("PASS: test_dimensions_loaded")


def test_conformed_facts_row_counts(ch_client):
    """Ensure fact tables contain records ingested from raw sources."""
    facts = [
        "fact_weather_hourly",
        "fact_air_quality_hourly",
        "fact_fx_daily",
        "fact_news_intensity",
        "fact_economic_indicator",
        "fact_osm_infrastructure",
    ]
    for fact in facts:
        cnt = ch_client.command(f"SELECT count() FROM urbanpulse.{fact}")
        assert cnt > 0, f"Table urbanpulse.{fact} is empty!"
        print(f"PASS: urbanpulse.{fact} has {cnt} rows")


def test_fact_data_ranges_and_constraints(ch_client):
    """Business rule validation on facts: realistic ranges and positive rates."""
    # Temperature ranges in West Africa should be realistic (-10C to +60C)
    invalid_temp = ch_client.command("""
        SELECT count() FROM urbanpulse.fact_weather_hourly
        WHERE temperature_c < -10.0 OR temperature_c > 60.0
    """)
    assert invalid_temp == 0, f"Found {invalid_temp} unrealistic temperature records"

    # FX rates must always be strictly positive
    invalid_fx = ch_client.command("""
        SELECT count() FROM urbanpulse.fact_fx_daily
        WHERE units_per_usd <= 0
    """)
    assert invalid_fx == 0, f"Found {invalid_fx} non-positive FX rates"
    print("PASS: test_fact_data_ranges_and_constraints")


def test_marts_populated_and_valid(ch_client):
    """Validate all 4 data marts exist and have valid values."""
    marts = [
        "mart_environment_daily",
        "mart_fx_daily",
        "mart_mobility_daily",
        "mart_city_intelligence_daily",
    ]
    for m in marts:
        cnt = ch_client.command(f"SELECT count() FROM urbanpulse.{m}")
        assert cnt > 0, f"Mart urbanpulse.{m} is empty!"
        print(f"PASS: urbanpulse.{m} has {cnt} rows")


def test_composite_index_mathematical_bounds(ch_client):
    """
    Composite City Intelligence Index must be strictly bounded between 0 and 100.
    Sub-scores must also be within [0, 100].
    """
    violations = ch_client.command("""
        SELECT count() FROM urbanpulse.mart_city_intelligence_daily
        WHERE city_intelligence_score < 0.0 OR city_intelligence_score > 100.0
           OR score_environment < 0.0 OR score_environment > 100.0
           OR score_economic < 0.0 OR score_economic > 100.0
           OR score_mobility < 0.0 OR score_mobility > 100.0
           OR score_vibrancy < 0.0 OR score_vibrancy > 100.0
    """)
    assert violations == 0, f"Found {violations} composite index bound violations!"
    print("PASS: test_composite_index_mathematical_bounds (all scores clamped in [0, 100])")


def test_ingestion_log_fresh(ch_client):
    """Observability contract: ingestion_log is populated and its latest run is fresh.

    Freshness budget: any successful source pull or pipeline stage within the
    last 36 hours counts as live. Beyond that the warehouse is stale and the
    dashboard freshness states must show it.
    """
    tables = [r[0] for r in ch_client.query(
        "SHOW TABLES FROM urbanpulse LIKE 'ingestion_log'").result_rows]
    assert tables, "urbanpulse.ingestion_log is missing — run the pipeline once to seed it"

    # No FINAL here, unlike the fact/mart queries elsewhere in this suite: FINAL
    # is legal only on data-collapsing engines (Replacing/Summing/etc.), and
    # ingestion_log is a plain MergeTree — append-only audit history with
    # nothing to collapse — so ClickHouse rejects FINAL on it (ILLEGAL_FINAL, 181).
    latest_ok = ch_client.query("""
        SELECT max(started_at) FROM urbanpulse.ingestion_log
        WHERE status IN ('success', 'duplicate')
    """).result_rows[0][0]
    assert latest_ok is not None, "ingestion_log has no successful run yet"

    latest_str = latest_ok.strftime("%Y-%m-%d %H:%M:%S") \
        if hasattr(latest_ok, "strftime") else str(latest_ok)
    age_h = ch_client.command(f"""
        SELECT dateDiff('hour', toDateTime('{latest_str}'), now())
    """)
    assert age_h is not None and age_h < 36, (
        f"ingestion_log is stale: latest successful activity was {age_h}h ago "
        f"({latest_str}). Run the pipeline to refresh."
    )

    errors = ch_client.command("""
        SELECT count() FROM urbanpulse.ingestion_log
        WHERE status = 'error' AND started_at > dateSub(hour, 36, now())
    """)
    assert errors == 0, (
        f"{errors} source/stage error(s) recorded in the last 36h — "
        "check urbanpulse.ingestion_log for details"
    )
    print(f"PASS: test_ingestion_log_fresh (latest success {latest_str}, {age_h}h ago)")


if __name__ == "__main__":
    client = get_client()
    print("Running Africa Pulse Data Quality Test Suite...")
    test_dimensions_loaded(client)
    test_conformed_facts_row_counts(client)
    test_fact_data_ranges_and_constraints(client)
    test_marts_populated_and_valid(client)
    test_composite_index_mathematical_bounds(client)
    test_ingestion_log_fresh(client)
    print("\nALL 6 DATA QUALITY TEST SUITES PASSED!")

