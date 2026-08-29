from __future__ import annotations

import time
from typing import Optional

import requests


class RateLimitedSession:
    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "galen-density-map/0.1 (scholarly research; local pipeline)"}
        )

    def get(self, url: str) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.rate_limit_seconds:
                time.sleep(self.rate_limit_seconds - elapsed)
            try:
                resp = self.session.get(url, timeout=self.timeout_seconds)
                self._last_request = time.monotonic()
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.rate_limit_seconds * attempt)
                    continue
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(self.rate_limit_seconds * attempt)
        raise RuntimeError(f"Failed to GET {url}: {last_exc}")


def rate_limited_get(
    url: str,
    rate_limit_seconds: float = 1.0,
    timeout_seconds: float = 60.0,
    max_retries: int = 3,
) -> requests.Response:
    return RateLimitedSession(
        rate_limit_seconds=rate_limit_seconds,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    ).get(url)
