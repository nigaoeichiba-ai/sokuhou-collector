"""Minimal polite HTTP fetch for public-information sources."""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass
import ssl

USER_AGENT = "sokuhou-collector/0.1 (+https://github.com/nigaoeichiba-ai/sokuhou-collector)"


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    body: bytes
    last_modified: str | None
    etag: str | None


def _legacy_tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    return ctx


def fetch(url: str, timeout: float = 20.0, legacy_tls: bool = False) -> Fetched:
    """One GET request. No retries: callers decide when to try again."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = _legacy_tls_context() if legacy_tls else None
    with urllib.request.urlopen(req, timeout=timeout, context=context) as res:
        return Fetched(
            url=url,
            status=res.status,
            body=res.read(),
            last_modified=res.headers.get("Last-Modified"),
            etag=res.headers.get("ETag"),
        )
