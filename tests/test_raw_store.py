"""Idempotency tests for the raw evidence store (brief §13: repeated execution
must not silently multiply records)."""
from ingestion.common.raw_store import RawStore


def test_same_payload_is_not_stored_twice(tmp_path):
    store = RawStore(tmp_path)
    payload = {"time": ["2026-09-23T00:00"], "temperature_2m": [27.4]}
    _, digest1, created1 = store.save("test_source", "ng_lagos", payload)
    _, digest2, created2 = store.save("test_source", "ng_lagos", payload)
    assert digest1 == digest2
    assert created1 is True
    assert created2 is False


def test_different_payload_gets_new_checksum(tmp_path):
    store = RawStore(tmp_path)
    _, d1, _ = store.save("test_source", "ng_lagos", {"a": 1})
    _, d2, _ = store.save("test_source", "ng_lagos", {"a": 2})
    assert d1 != d2
