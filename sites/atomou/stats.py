"""Reads the daily count files written by api/e.php (<site folder>/stats/YYYY-MM-DD.json) and says which skins, home layouts and actions are liked.

    python sites/atomou/stats.py <folder with the daily files> [--days 30]

Only counts exist: the files hold no text, dates, ids or addresses."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def load(folder: Path, days: int = 30, today: date | None = None) -> Counter:
    today = today or date.today()
    since = (today - timedelta(days=days)).isoformat()
    total: Counter = Counter()
    for f in sorted(folder.iterdir()):
        if DAY.match(f.name) and f.stem >= since:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            for k, v in data.items():
                if isinstance(v, int):
                    total[k] += v
    return total


def group(total: Counter, prefix: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for k, v in total.items():
        head, _, rest = k.partition(":")
        if head == prefix and rest:
            out[rest] += v
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def summary(total: Counter) -> dict:
    skins_in_use = group(total, "skin")
    uses = sum(skins_in_use.values()) or 1
    acts = group(total, "act")
    views = group(total, "view")
    return {
        "page_views": sum(views.values()),
        "views_by_page": views,
        "skin_share_of_views": {k: round(v / uses, 3) for k, v in skins_in_use.items()},
        "skin_picked": {k.split(":", 1)[1]: v for k, v in acts.items() if k.startswith("skin:")},
        "home_layouts": group(total, "home_order"),
        "blocks_hidden_on_views": group(total, "home_hidden"),
        "block_hide_clicks": {k.split(":", 1)[1]: v for k, v in acts.items() if k.startswith("block_hide:")},
        "actions": {k: v for k, v in acts.items() if ":" not in k},
        "added_by_kind": {k.split(":", 1)[1]: v for k, v in acts.items() if k.startswith("add:")},
        "big_text_views": total.get("big:on", 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    print(json.dumps(summary(load(Path(a.folder), a.days)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
