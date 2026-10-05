"""Minimal polite HTTP fetch for public-information sources."""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass

USER_AGENT = "sokuhou-collector/0.1 (+https://github.com/nigaoeichiba-ai/sokuhou-collector)"


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    body: bytes
    last_modified: str | None
    etag: str | None


def fetch(url: str, timeout: float = 20.0) -> Fetched:
    """One GET request. No retries: callers decide when to try again."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return Fetched(
            url=url,
            status=res.status,
            body=res.read(),
            last_modified=res.headers.get("Last-Modified"),
            etag=res.headers.get("ETag"),
        )
