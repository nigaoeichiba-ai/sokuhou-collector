"""Tells a person that a survey of theirs got new answers (run by .github/workflows/yorokobu-ask-push.yml every ten minutes).

    python -m sites.yorokobu.ask_push --dir <folder with the subscription files> --versions <json {survey id: answers so far}> [--dry-run]

The server keeps, per subscription (a browser of the person who made surveys), only the push endpoint, the two keys the browser made and the list of
{survey id, number of answers already announced}.  The message carries nothing but "there is something new"; the text of the notification is made by the
service worker on the device.  So no answer, and no content of a survey, ever goes through a push service.

The private VAPID key comes from the environment (YOROKOBU_VAPID_PRIVATE, or ATOMOU_VAPID_PRIVATE: the sites of the operator share one key pair); the
public half is config.json's vapid_public, and the two must belong together or every push is refused.
Output: counts only (never an endpoint); `gone.txt` (subscriptions the push service declared dead) and `notified.json` ({file: {survey id: answers announced}})
are written next to the subscriptions for the workflow to write back to the server.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sites.yorokobu import webpush

HERE = Path(__file__).resolve().parent
SUBJECT = "https://yorokobu-present.com"     # RFC 8292: a contact for the push service


def load(folder: Path) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(folder.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and isinstance(d.get("endpoint"), str) and isinstance(d.get("keys"), dict) and isinstance(d.get("watch"), list):
            out.append((p, d))
    return out


def due(sub: dict, versions: dict) -> dict:
    """{survey id: answers now} of the watched surveys that have more answers than were announced to this subscription."""
    out = {}
    for w in sub["watch"]:
        if not isinstance(w, dict) or not isinstance(w.get("id"), str):
            continue
        try:
            sent = int(w.get("sent", 0))
        except (TypeError, ValueError):
            continue
        now = versions.get(w["id"])
        if isinstance(now, int) and now > sent:
            out[w["id"]] = now
    return out


def payload(new: int) -> dict:
    return {"v": 1, "a": 1, "n": new}           # "new answers" and how many; the device says the rest itself


def run(folder: Path, versions: dict, key_text: str | None, *, dry_run: bool = False, opener=None, public: str | None = None) -> dict:
    subs = load(folder)
    changed = {p.name: due(s, versions) for p, s in subs}
    todo = [(p, s) for p, s in subs if changed[p.name]]
    notified: dict[str, dict] = {}
    counts = {"subscriptions": len(subs), "due": len(todo), "sent": 0, "gone": 0, "retry": 0, "failed": 0}
    if key_text:
        pub = public if public is not None else json.loads((HERE / "config.json").read_text(encoding="utf-8")).get("vapid_public") or ""
        counts["key_matches_config"] = webpush.b64u(webpush.public_bytes(webpush.load_private_key(key_text).public_key())) == pub
    gone: list[str] = []
    if dry_run or not todo:
        (folder / "gone.txt").write_text("", encoding="utf-8")
        (folder / "notified.json").write_text("{}", encoding="utf-8")
        return counts
    if not key_text:
        raise SystemExit("the VAPID private key is not set")
    if not counts.get("key_matches_config"):
        raise SystemExit("the VAPID private key does not belong to config.json vapid_public")
    key = webpush.load_private_key(key_text)
    for p, s in todo:
        new = sum(changed[p.name][i] - next((int(w.get("sent", 0)) for w in s["watch"] if w.get("id") == i), 0) for i in changed[p.name])
        r = webpush.send(s, payload(max(1, new)), key, SUBJECT, opener=opener)
        if 200 <= r.status < 300:
            counts["sent"] += 1
            notified[p.name] = changed[p.name]
        elif r.gone:
            counts["gone"] += 1
            gone.append(p.name)
        elif r.retry:
            counts["retry"] += 1
        else:
            counts["failed"] += 1
    (folder / "gone.txt").write_text("".join(n + "\n" for n in gone), encoding="utf-8")
    (folder / "notified.json").write_text(json.dumps(notified), encoding="utf-8")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--versions", required=True, help="a JSON file {survey id: answers so far} (what the server holds)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    versions = json.loads(Path(a.versions).read_text(encoding="utf-8"))
    key = os.environ.get("YOROKOBU_VAPID_PRIVATE") or os.environ.get("ATOMOU_VAPID_PRIVATE")
    counts = run(Path(a.dir), versions, key, dry_run=a.dry_run)
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
