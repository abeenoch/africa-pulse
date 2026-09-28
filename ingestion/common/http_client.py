
import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)


class SourceUnavailableError(Exception):
    """Raised when a source fails after all retries. Callers must record this
    event (not silently substitute data) per brief ."""


class HttpClient:
    def __init__(self, timeout: int = 30, user_agent: str = "africa-pulse-capstone/1.0"):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.timeout = timeout

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def get_json(self, url: str, params: dict | None = None) -> dict:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 429:
            log.warning("Rate limited by %s — backing off", url)
            raise requests.Timeout("429 rate limited")
        resp.raise_for_status()
        return resp.json()
