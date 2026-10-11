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

SLOTS = ("m", "e", "s")   # s: a shared card the subscription watches has a version newer than the one announced (no date involved)
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


def shared_due(sub: dict, versions: dict) -> dict:
    """{card id: newest version} of the watched cards that changed since this device saw them and since the last announcement."""
    out = {}
    for w in sub.get("watch") or []:
        if not isinstance(w, dict) or not isinstance(w.get("id"), str):
            continue
        try:
            seen, sent = int(w.get("ver", 0)), int(w.get("sent", 0))
        except (TypeError, ValueError):
            continue
        now = versions.get(w["id"], 0)
        if isinstance(now, int) and now > max(seen, sent):
            out[w["id"]] = now
    return out


def payload(today: str, slot: str) -> dict:
    if slot == "s":
        return {"v": 1, "s": "u"}      # "a card you follow was changed": nothing else; the device says the rest itself
    return {"v": 1, "d": today, "s": slot}


def run(folder: Path, today: str, slot: str, key_text: str | None, *, dry_run: bool = False, opener=None, public: str | None = None, versions: dict | None = None) -> dict:
    subs = load(folder)
    changed = {p.name: shared_due(s, versions or {}) for p, s in subs} if slot == "s" else {}
    due = [(p, s) for p, s in subs if (changed[p.name] if slot == "s" else is_due(s, today, slot))]
    notified: dict[str, dict] = {}
    counts = {"subscriptions": len(subs), "due": len(due), "sent": 0, "gone": 0, "retry": 0, "failed": 0}
    if key_text:   # the secret must be the private half of config.json's vapid_public, or every push is refused by the push services
        pub = public if public is not None else json.loads((Path(__file__).resolve().parent / "config.json").read_text(encoding="utf-8")).get("vapid_public") or ""
        counts["key_matches_config"] = webpush.b64u(webpush.public_bytes(webpush.load_private_key(key_text).public_key())) == pub
    gone: list[str] = []
    if dry_run or not due:
        (folder / "gone.txt").write_text("", encoding="utf-8")
        (folder / "notified.json").write_text("{}", encoding="utf-8")
        return counts
    if not key_text:
        raise SystemExit("ATOMOU_VAPID_PRIVATE is not set")
    if not counts.get("key_matches_config"):
        raise SystemExit("ATOMOU_VAPID_PRIVATE does not belong to config.json vapid_public")
    key = webpush.load_private_key(key_text)
    for p, s in due:
        r = webpush.send(s, payload(today, slot), key, SUBJECT, opener=opener)
        if 200 <= r.status < 300:
            counts["sent"] += 1
            if slot == "s":
                notified[p.name] = changed[p.name]
        elif r.gone:
            counts["gone"] += 1
            gone.append(p.name)
        elif r.retry:
            counts["retry"] += 1
        else:
            counts["failed"] += 1
    (folder / "gone.txt").write_text("".join(n + "\n" for n in gone), encoding="utf-8")
    (folder / "notified.json").write_text(json.dumps(notified), encoding="utf-8")   # file name -> {card id: version announced}: the workflow writes it back to the server
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--slot", choices=SLOTS, required=True)
    ap.add_argument("--today", default=today_jst())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--versions", default="", help="slot s: a JSON file {card id: version} (what the server holds)")
    a = ap.parse_args(argv)
    versions = json.loads(Path(a.versions).read_text(encoding="utf-8")) if a.versions else {}
    counts = run(Path(a.dir), a.today, a.slot, os.environ.get("ATOMOU_VAPID_PRIVATE"), dry_run=a.dry_run, versions=versions)
    print(json.dumps({"today": a.today, "slot": a.slot, **counts}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
