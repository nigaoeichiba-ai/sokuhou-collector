"""atomou.com 人気の日, on the server itself (run by server_live.sh about once an hour): reads the daily count files of api/e.php (<site folder>/stats/YYYY-MM-DD.json) and writes
live/pop.v1.json: the public days that most people put into their planner in the last 30 days, in order.

    python3 server_pop.py <stats folder> <output file> [--days 30] [--min 3] [--top 30]

Only counts exist in the daily files (no text, no addresses).  The output holds the ids in order and NO numbers; a day needs at least --min saves to appear at all, so that one
person's own choice is never a "popular" day.  Python 3.6 of the server: no `from __future__`, no new syntax."""
import argparse
import json
import os
import re
import sys
from datetime import date, timedelta

DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
KEY = re.compile(r"^act:pop:([0-9a-f]{10})$")


def popular(folder, today=None, days=30, minimum=3, top=30):
    today = today or date.today()
    since = (today - timedelta(days=days)).isoformat()
    total = {}
    for name in sorted(os.listdir(folder)):
        m = DAY.match(name)
        if not m or m.group(1) < since:
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            continue
        for k, v in data.items():
            km = KEY.match(k)
            if km and isinstance(v, int) and v > 0:
                total[km.group(1)] = total.get(km.group(1), 0) + v
    ranked = sorted((i for i, n in total.items() if n >= minimum), key=lambda i: (-total[i], i))
    return {"v": 1, "days": days, "items": [{"id": i} for i in ranked[:top]]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args(argv)
    if not os.path.isdir(a.folder):
        data = {"v": 1, "days": a.days, "items": []}   # no counts yet (nobody has sent any)
    else:
        data = popular(a.folder, days=a.days, minimum=a.min, top=a.top)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, a.out)
    print("pop: %d days listed" % len(data["items"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
