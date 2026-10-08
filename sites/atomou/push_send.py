"""Sends the day's push notifications (run by .github/workflows/atomou-push.yml twice a day, after it copied the subscription folder from the server).

    python -m sites.atomou.push_send --dir <folder with the subscription files> --slot m|e [--today YYYY-MM-DD] [--dry-run]

The server holds, per subscription, only the endpoint, the two keys and the days on which to knock ("dates": [{"d": "2026-10-20", "s": "m"}]):
no titles, no names.  The message itself carries nothing but the day and the slot; the service worker on the device looks up what
that day means in its own local mirror and shows the notification text from there.  So the content of a reminder never leaves the device.

Slots: m = morning (07:00 JST), e = evening (21:00 JST, "the night before").
The private VAPID key comes from the environment (ATOMOU_VAPID_PRIVATE); the public key is in config.json.
Output: counts only (never an endpoint), plus `gone.txt` in the folder: the file names whose subscription the push service declared dead (404/410),
so that the workflow can delete them on the server.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sites.atomou import webpush

SLOTS = ("m", "e")
SUBJECT = "https://atomou.com"   # RFC 8292: a contact for the push service (mailto: or https:)


def today_jst() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")


def load(folder: Path) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(folder.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and isinstance(d.get("endpoint"), str) and isinstance(d.get("keys"), dict) and isinstance(d.get("dates"), list):
            out.append((p, d))
    return out


def is_due(sub: dict, today: str, slot: str) -> bool:
    return any(isinstance(x, dict) and x.get("d") == today and x.get("s", "m") == slot for x in sub["dates"])


def payload(today: str, slot: str) -> dict:
    return {"v": 1, "d": today, "s": slot}


def run(folder: Path, today: str, slot: str, key_text: str | None, *, dry_run: bool = False, opener=None) -> dict:
    subs = load(folder)
    due = [(p, s) for p, s in subs if is_due(s, today, slot)]
    counts = {"subscriptions": len(subs), "due": len(due), "sent": 0, "gone": 0, "retry": 0, "failed": 0}
    gone: list[str] = []
    if dry_run or not due:
        (folder / "gone.txt").write_text("", encoding="utf-8")
        return counts
    if not key_text:
        raise SystemExit("ATOMOU_VAPID_PRIVATE is not set")
    key = webpush.load_private_key(key_text)
    for p, s in due:
        r = webpush.send(s, payload(today, slot), key, SUBJECT, opener=opener)
        if 200 <= r.status < 300:
            counts["sent"] += 1
        elif r.gone:
            counts["gone"] += 1
            gone.append(p.name)
        elif r.retry:
            counts["retry"] += 1
        else:
            counts["failed"] += 1
    (folder / "gone.txt").write_text("".join(n + "\n" for n in gone), encoding="utf-8")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--slot", choices=SLOTS, required=True)
    ap.add_argument("--today", default=today_jst())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    counts = run(Path(a.dir), a.today, a.slot, os.environ.get("ATOMOU_VAPID_PRIVATE"), dry_run=a.dry_run)
    print(json.dumps({"today": a.today, "slot": a.slot, **counts}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
