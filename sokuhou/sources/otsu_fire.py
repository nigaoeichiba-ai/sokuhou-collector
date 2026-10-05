"""Otsu City fire department dispatch page (public info).

Source: http://www.otsu119.jp/fire/saigai/saigaiPc.html (Shift_JIS, http only).
Each <li> holds one message. A header timestamp is followed by either
  - a start message:      "<place>で<kind>が発生し、消防車等が出動しています。"
  - a resolution message: "<place>の<kind>は、<time>に<result>しました。"
For a resolution the header timestamp repeats the START time, so
(start time, place, kind) identifies one incident.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone

from sokuhou.http import fetch

URL = "http://www.otsu119.jp/fire/saigai/saigaiPc.html"
JST = timezone(timedelta(hours=9))

_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
def _ts(prefix: str) -> str:
    return rf"(?P<{prefix}mo>\d{{2}})月(?P<{prefix}d>\d{{2}})日\s*(?P<{prefix}h>\d{{2}})時(?P<{prefix}mi>\d{{2}})分"


_START = re.compile(
    rf"^{_ts('s')}\s*(?P<place>.+?付近|.+?)で(?P<kind>.+?)が発生し、\s*消防車等が出動しています"
)
_RESOLVED = re.compile(
    rf"^{_ts('s')}\s*(?P<place>.+?付近|.+?)の(?P<kind>.+?)は、\s*{_ts('r')}に(?P<result>.+?)しました"
)
_NO_INCIDENT = "火事などの災害は発生していません"


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", fragment)).strip()


def _when(now: datetime, m: re.Match, prefix: str) -> datetime:
    """The page omits the year: take the latest year that is not in the future."""
    candidate = datetime(
        now.year, int(m[f"{prefix}mo"]), int(m[f"{prefix}d"]),
        int(m[f"{prefix}h"]), int(m[f"{prefix}mi"]), tzinfo=JST,
    )
    if candidate > now + timedelta(days=1):
        candidate = candidate.replace(year=now.year - 1)
    return candidate


def parse(html: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(JST)
    incidents: dict[tuple[str, str, str], dict] = {}
    unparsed: list[str] = []  # messages that match neither pattern: the page layout may have changed
    for li in _LI.findall(html):
        text = _text(li)
        if not (_START.match(text) or _RESOLVED.match(text)) and _NO_INCIDENT not in text:
            unparsed.append(text)
        m = _START.match(text)
        if m:
            started = _when(now, m, "s")
            key = (started.isoformat(), m["place"], m["kind"])
            incidents.setdefault(key, {"started_at": started.isoformat(), "place": m["place"], "kind": m["kind"]})
            continue
        m = _RESOLVED.match(text)
        if m:
            started = _when(now, m, "s")
            resolved = _when(now, m, "r")
            key = (started.isoformat(), m["place"], m["kind"])
            rec = incidents.setdefault(key, {"started_at": started.isoformat(), "place": m["place"], "kind": m["kind"]})
            rec["resolved_at"] = resolved.isoformat()
            rec["result"] = m["result"]
    events = sorted(incidents.values(), key=lambda e: e["started_at"], reverse=True)
    for e in events:
        e["status"] = "resolved" if "resolved_at" in e else "reported"
    return {
        "source": URL,
        "fetched_at": now.isoformat(),
        "no_active_incident": _NO_INCIDENT in html_text_of(html),
        "unparsed": unparsed,
        "incidents": events,
    }


def html_text_of(html: str) -> str:
    return _text(html)


def collect() -> dict:
    res = fetch(URL)
    return parse(res.body.decode("cp932", errors="replace"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
