"""jGrants public API: subsidies currently accepting applications.

No authentication. Required query params: keyword (2+ chars), sort, order, acceptance.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import datetime, timezone

from sokuhou.http import fetch

BASE = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
DETAIL = "https://www.jgrants-portal.go.jp/subsidy/{id}"
KEEP = (
    "id", "name", "title", "subsidy_max_limit", "acceptance_start_datetime",
    "acceptance_end_datetime", "target_area_search", "target_number_of_employees",
    "institution_name",
)


def build_url(keyword: str) -> str:
    q = {"keyword": keyword, "sort": "acceptance_end_datetime", "order": "ASC", "acceptance": "1"}
    return f"{BASE}?{urllib.parse.urlencode(q)}"


def parse(payload: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    items = []
    for raw in payload.get("result", []):
        item = {k: raw.get(k) for k in KEEP}
        item["detail_url"] = DETAIL.format(id=raw["id"])
        items.append(item)
    return {"source": BASE, "fetched_at": now.isoformat(), "total": len(items), "subsidies": items}


def collect(keyword: str = "補助金") -> dict:
    res = fetch(build_url(keyword))
    return parse(json.loads(res.body.decode("utf-8")))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
