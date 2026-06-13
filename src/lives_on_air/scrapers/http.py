from __future__ import annotations

import time
from pathlib import Path

import requests

from lives_on_air.config import REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS


class FetchError(RuntimeError):
    pass


def fetch_text(url: str, cache_path: Path | None = None, delay_seconds: float = 1.0) -> str:
    """Fetch a URL with a small delay and optional raw HTML cache."""
    if cache_path and cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    time.sleep(delay_seconds)
    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise FetchError(f"{response.status_code} while fetching {url}")

    response.encoding = response.encoding or "utf-8"
    text = response.text
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return text
