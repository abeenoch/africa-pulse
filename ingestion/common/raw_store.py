"""Immutable raw-evidence store .

Every payload is written once, keyed by SHA-256 checksum, so repeated ingestion
of the same observation is idempotent."""
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class RawStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def checksum(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def save(self, source: str, city_id: str, payload: dict) -> tuple[Path, str, bool]:
        """Persist raw payload + ingestion metadata.

        Returns (path, checksum, created). created=False means we already had
        this exact observation — caller must skip downstream inserts."""
        digest = self.checksum(payload)
        now = datetime.now(timezone.utc)
        folder = self.base_dir / source / city_id / now.strftime("%Y/%m/%d")
        folder.mkdir(parents=True, exist_ok=True)
        # Dedup is keyed on checksum, not arrival second: if this exact payload
        # was stored at any time today, it is a duplicate delivery.
        existing = list(folder.glob(f"*_{digest[:12]}.json"))
        if existing:
            return existing[0], digest, False
        path = folder / f"{now.strftime('%H%M%S')}_{digest[:12]}.json"
        envelope = {
            "checksum": digest,
            "source": source,
            "city_id": city_id,
            "ingested_at_utc": now.isoformat(),  # ingestion time 
            "payload": payload,
        }
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=1), encoding="utf-8")
        return path, digest, True
