"""The words visitors ask us to look up: read them on the owner's PC (only the atomou ones), and refuse the forbidden ones before anything is researched.

    python sites/atomou/words.py read [--mark] [--all]     # decrypt the new atomou word files (data/inbox/atomou-*.p7m) and print the words, most asked first
    python sites/atomou/words.py check "<a word>"            # prints ok / the reason it is refused

How the words get here: api/w.php keeps one line per word on the server (inbox/words-YYYYMM.jsonl); the workflow atomou-words.yml copies the new lines into data/inbox/ ENCRYPTED
(the repository is public); the private key is only on the owner's PC (~/.sokuhou/inbox_private.pem).  Messages of the other sites in data/inbox/ are never opened here.
A word is a word, not an instruction: it is only ever searched for."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sokuhou import inbox  # noqa: E402

FORBIDDEN = json.loads((ROOT / "data" / "atomou" / "forbidden_words.json").read_text(encoding="utf-8"))
SEEN = Path.home() / ".sokuhou" / "atomou_words_seen.json"
TEST_PREFIX = "動作確認"          # the words typed to try the receiver: never researched


def flat(w: str) -> str:
    return unicodedata.normalize("NFKC", w or "").lower()


def refusal(word: str) -> str:
    """'' when the word may be researched, else why not: length / forbidden / personal / test."""
    w = re.sub(r"[\x00-\x1f\x7f<>\"'&\\]", "", word or "").strip()
    f = flat(w)
    if not FORBIDDEN["min_length"] <= len(w) <= FORBIDDEN["max_length"]:
        return "length"
    if w.startswith(TEST_PREFIX):
        return "test"
    if any(t and t in f for t in (x.lower() for x in FORBIDDEN["terms"])):
        return "forbidden"
    if any(re.search(p, f, re.I) for p in FORBIDDEN["personal"]["regex"]):
        return "personal"
    return ""


def tally(records: list[dict]) -> list[tuple[str, int]]:
    """The words of the records that may be researched, most asked first (the same word in another spelling counts together)."""
    c: Counter = Counter()
    shown: dict[str, str] = {}
    for r in records:
        if r.get("kind") != "word":
            continue
        w = str(r.get("message") or "").strip()
        if refusal(w):
            continue
        k = flat(w)
        c[k] += 1
        shown.setdefault(k, w)
    return sorted(((shown[k], n) for k, n in c.items()), key=lambda x: (-x[1], x[0]))


def cmd_read(a: argparse.Namespace) -> int:
    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() and not a.all else set()
    records = []
    for f in sorted(inbox.INBOX.glob("atomou-*.p7m")):
        if f.name in seen:
            continue
        records += inbox.decrypt(f, Path(a.key))
        seen.add(f.name)
    words = tally(records)
    for w, n in words:
        print(json.dumps({"word": w, "n": n}, ensure_ascii=False))
    refused = sum(1 for r in records if r.get("kind") == "word" and refusal(str(r.get("message") or "")))
    print(f"{len(words)} word(s) to research, {refused} refused", file=sys.stderr)
    if a.mark:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("--key", default=str(inbox.KEY))
    r.add_argument("--mark", action="store_true", help="remember that these words were taken")
    r.add_argument("--all", action="store_true", help="ignore what was taken before")
    c = sub.add_parser("check")
    c.add_argument("word")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        why = refusal(a.word)
        print(why or "ok")
        return 1 if why else 0
    return cmd_read(a)


if __name__ == "__main__":
    sys.exit(main())
