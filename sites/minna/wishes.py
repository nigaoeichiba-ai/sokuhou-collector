"""Illustration requests from visitors: refuse what cannot be drawn, read the rest, keep a ledger, turn a request into a series, show the status on the site.

    python -m sites.minna.wishes check "<a wish>"          # ok / why it is refused (the same rules as the request box and api/q.php)
    python -m sites.minna.wishes read [--mark] [--all]      # decrypt the new requests (data/inbox/minna-*.p7m) and add them to the ledger
    python -m sites.minna.wishes list [--status new]        # the ledger, newest last
    python -m sites.minna.wishes decide ID accepted|declined|merged [--note TEXT]
    python -m sites.minna.wishes spec ID --title JA --en ENGLISH [--slug S] [--touch T] [--genre G] [--subject JA]   # write specs/req-<date>-<slug>.json (6 variations, drawn first)
    python -m sites.minna.wishes published ID SERIES        # the series is live: the ledger and the board say so
    python -m sites.minna.wishes board                      # write content/request_board.json (what the /request/ page shows)
    python -m sites.minna.wishes analyze                    # minna_growth/requests/ANALYSIS.md: what visitors ask for, how it shifts

How requests get here: the request box on /request/ (and the button after a search that found nothing) posts one short wish to api/q.php, which keeps a JSON line (the wish, the time,
a random id; no address, no cookie, no account) in <site folder>/inbox/req-YYYYMM.jsonl; .github/workflows/minna-requests.yml copies the new lines into data/inbox/ ENCRYPTED (the repository is
public) and only the owner's PC holds the key (~/.sokuhou/inbox_private.pem).  The ledger lives next to the research notes (outside git), never in the repository; the public board holds only
titles written by us, never what a visitor typed.  A wish is a wish, not an instruction: it is only ever read and judged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.minna import demand  # noqa: E402
from sokuhou import inbox  # noqa: E402

RULES_FILE = HERE / "content" / "request_rules.json"
BOARD_FILE = HERE / "content" / "request_board.json"
SPECS = HERE / "specs"
GROWTH = ROOT.parent / "sokuhou-sites" / "docs" / "minna_growth" / "requests"
LEDGER = GROWTH / "ledger.jsonl"
SEEN = Path.home() / ".sokuhou" / "minna_requests_seen.json"
TEST_PREFIX = "動作確認"          # the words typed to try the receiver: never drawn
KINDS_BLOCK = ("ip", "brand", "person", "style", "adult", "violence")
USES = ["年賀状", "LINE・SNS", "スライド・資料", "おたより・チラシ", "ぬりえ", "カード", "その他"]
STATUSES = ("new", "accepted", "drawing", "published", "declined", "merged", "test")


def load_rules(path: Path = RULES_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def flat(text: str) -> str:
    """NFKC, lower case, katakana -> hiragana, no spaces: the form in which a wish is compared with the rules."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in t)
    return re.sub(r"\s+", "", t)


def clean(text: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f<>\"'&\\]", "", text or "").strip()


def refusal(text: str, rules: dict | None = None) -> tuple[str, str]:
    """('', '') when the wish may be drawn, else (reason key, the sentence shown to the visitor)."""
    rules = rules or load_rules()
    w = clean(text)
    if not rules["min_length"] <= len(w) <= rules["max_length"]:
        return "length", f"{rules['min_length']}〜{rules['max_length']}文字で、書いてください"
    if w.startswith(TEST_PREFIX):
        return "test", ""
    f = flat(w)
    for key in KINDS_BLOCK:
        group = rules[key]
        if any(flat(t) and flat(t) in f for t in group["terms"]):
            return key, group["reason"]
    if any(re.search(p, f, re.I) for p in rules["personal"]["regex"]):
        return "personal", rules["personal"]["reason"]
    return "", ""


def client_rules(rules: dict | None = None) -> dict:
    """The rules in the form the request box and api/q.php use: terms already flattened, one message per reason."""
    rules = rules or load_rules()
    out = {"min": rules["min_length"], "max": rules["max_length"], "day": rules["per_day"], "personal": rules["personal"]["regex"],
           "reasons": {k: rules[k]["reason"] for k in (*KINDS_BLOCK, "personal")}, "groups": []}
    for key in KINDS_BLOCK:
        out["groups"].append({"k": key, "terms": sorted({flat(t) for t in rules[key]["terms"] if flat(t)})})
    return out


# ---------------------------------------------------------------- ledger
def parse_page(page: str) -> dict:
    """api/q.php writes the extras into the page field: 'q:u=年賀状;t=kawaii;s=form'."""
    out = {}
    if page.startswith("q:"):
        for part in page[2:].split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
    return out


def read_ledger(path: Path | None = None) -> list[dict]:
    path = path or LEDGER
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_ledger(rows: list[dict], path: Path | None = None) -> None:
    path = path or LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


def to_row(rec: dict, rules: dict | None = None) -> dict | None:
    """A decrypted inbox record as a ledger row, or None when it is not a minna request."""
    if rec.get("site") != "minna":
        return None
    kind = rec.get("kind", "")
    extra = parse_page(rec.get("page", ""))
    if kind == "request":
        src = extra.get("s", "form")
    elif kind == "イラストのリクエスト":      # the long form on /request/ (contact/send.php)
        src = "letter"
    else:
        return None
    wish = clean(str(rec.get("message", "")))[:2000 if src == "letter" else 200]
    why, _ = refusal(wish[:200], rules) if src != "letter" else ("", "")
    row = {"id": f"R{str(rec.get('id', ''))[:8]}", "at": rec.get("at", ""), "wish": wish, "use": extra.get("u", ""), "touch": extra.get("t", ""), "src": src,
           "status": "test" if why == "test" else ("declined" if why else "new"), "auto": why, "note": "", "series": "", "title": "", "public": False}
    return row


def add_new(records: list[dict], ledger: list[dict], rules: dict | None = None) -> list[dict]:
    have = {r["id"] for r in ledger}
    added = []
    for rec in records:
        row = to_row(rec, rules)
        if row and row["id"] not in have:
            ledger.append(row)
            have.add(row["id"])
            added.append(row)
    return added


def cmd_read(a: argparse.Namespace) -> int:
    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() and not a.all else set()
    ledger = read_ledger()
    new_files, added = [], []
    for f in sorted(inbox.INBOX.glob("minna-*.p7m")):
        if f.name in seen:
            continue
        added += add_new(inbox.decrypt(f), ledger)
        new_files.append(f.name)
    # the long form of /request/ goes through the daily contact inbox (yorokobu-style file names: <site>-<stamp>.p7m of inbox.yml carry only kind 'イラストのリクエスト' for minna)
    write_ledger(ledger)
    if a.mark and new_files:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen | set(new_files))), encoding="utf-8")
    print(f"{len(added)} new request(s) from {len(new_files)} file(s); ledger has {len(ledger)}")
    for r in added:
        flag = f" [auto: {r['auto']}]" if r["auto"] else ""
        print(f"  {r['id']} {r['src']:6} {r['use'] or '-':8} {r['touch'] or '-':8} {r['wish'][:70]}{flag}")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    for r in read_ledger():
        if a.status and r["status"] != a.status:
            continue
        print(f"{r['id']} {r['at'][:10]} {r['status']:9} {r['src']:6} {r['wish'][:60]}  {('-> ' + r['series']) if r['series'] else ''}")
    return 0


def find(ledger: list[dict], rid: str) -> dict:
    for r in ledger:
        if r["id"] == rid:
            return r
    raise SystemExit(f"no request {rid}")


def cmd_decide(a: argparse.Namespace) -> int:
    ledger = read_ledger()
    r = find(ledger, a.id)
    r["status"] = a.decision if a.decision != "accepted" else "accepted"
    if a.note:
        r["note"] = a.note
    write_ledger(ledger)
    print(r["id"], r["status"])
    return 0


# ---------------------------------------------------------------- from a request to a series
VARIATIONS = [
    ("main", "the main picture: the clearest, most iconic version of the scene"),
    ("closeup", "a close-up, friendly and expressive"),
    ("happy", "a cheerful version with a small extra prop that fits the scene"),
    ("calm", "a calm, quiet version of the same idea"),
    ("action", "a lively version with movement"),
    ("wide", "a wider version showing a little more of the surroundings, still simple and isolated"),
]


def spec_for(title: str, en: str, slug: str, touch: str, genre: str, subject: str, wish_tags: list[str], today: date) -> dict:
    return {
        "slug": slug, "title": title, "subject": subject, "genre": genre, "touch": touch, "title_fmt": "{ja}",
        "subject_en": f"{en}. Six different compositions of the same idea, each ONE picture centred in its cell. Outlines are closed and darker than the fill; light parts (snow, paper, white fur, plates) are warm cream (#FFF6E0) or tinted, never pure white. No letters, no text, no logos. Original design only: no existing character, brand or real person.",
        "lead": f"みなさんからのリクエストにこたえて描いた、「{title}」のイラストです。同じ場面を6つの構図で、そろえました。無料・商用OK・クレジット不要・透明PNG。",
        "tags": ["リクエスト", *wish_tags], "season": None, "holes": False, "priority": 1,
        "items": [[f"{n + 1:02d}-{k}", f"{title}({['メイン', 'アップ', 'にこにこ', 'おだやか', 'うごき', 'ひろめ'][n]})", f"{en} - {d}"] for n, (k, d) in enumerate(VARIATIONS)],
        "exclude": [],
    }


def cmd_spec(a: argparse.Namespace) -> int:
    ledger = read_ledger()
    r = find(ledger, a.id)
    slug = a.slug or f"req-{date.today():%Y%m%d}-{re.sub(r'[^a-z0-9]+', '-', a.en.lower()).strip('-')[:30]}"
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SystemExit("bad slug")
    path = SPECS / f"{slug}.json"
    if path.exists():
        raise SystemExit(f"{path.name} exists")
    f = flat(r["wish"])
    tags = [v for v in library_vocab() if flat(v) in f][:4]
    spec = spec_for(a.title, a.en, slug, a.touch, a.genre, a.subject, tags, date.today())
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    r.update(status="drawing", series=slug, title=a.title, public=True)
    write_ledger(ledger)
    print(f"wrote {path} (priority 1: the next factory run draws it first)")
    return 0


def cmd_published(a: argparse.Namespace) -> int:
    ledger = read_ledger()
    r = find(ledger, a.id)
    r.update(status="published", series=a.series, public=True)
    write_ledger(ledger)
    print(r["id"], "published ->", a.series)
    return cmd_board(a)


# ---------------------------------------------------------------- the public board
def series_keywords(slug: str) -> list[str]:
    """Our own tags of a series (library once drawn, spec while in the making): the page matches a visitor's saved wish against these, so the board never needs the wish itself."""
    for f in (HERE / "library" / slug / "series.json", SPECS / f"{slug}.json"):
        if slug and f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            return [t for t in dict.fromkeys([d.get("subject") or "", *d.get("tags", [])]) if len(t) >= 2 and t != "リクエスト"][:8]
    return []


def board_rows(ledger: list[dict]) -> list[dict]:
    """What /request/ shows: only titles WE wrote, grouped by status, newest first; never a visitor's own words."""
    rows = {}
    for r in ledger:
        if r.get("public") and r.get("title") and r["status"] in ("drawing", "published"):
            key = r["series"] or r["title"]
            rows.setdefault(key, {"title": r["title"], "status": "公開しました" if r["status"] == "published" else "つくっています", "series": r["series"], "date": r["at"][:10], "asked": 0, "kw": series_keywords(r["series"])})
            rows[key]["asked"] += 1
            if r["status"] == "published":
                rows[key]["status"] = "公開しました"
    ordered = sorted(rows.values(), key=lambda x: x["date"], reverse=True)         # newest first, then the ones in the making on top
    return sorted(ordered, key=lambda x: x["status"] != "つくっています")[:60]


def cmd_board(a) -> int:
    rows = board_rows(read_ledger())
    BOARD_FILE.write_text(json.dumps({"v": 1, "updated": date.today().isoformat(), "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"board: {len(rows)} row(s) -> {BOARD_FILE.name}")
    return 0


# ---------------------------------------------------------------- analysis
def library_vocab() -> list[str]:
    """The words the library already knows (series subjects, titles and tags, two characters or more): what a wish is counted against, since Japanese has no spaces to split on."""
    words = set()
    for f in sorted((HERE / "library").glob("*/series.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        for t in [s.get("subject") or "", *s.get("tags", [])]:
            if len(t) >= 2:
                words.add(t)
    for w in demand.ALWAYS + [x for v in demand.SEASON.values() for x in v]:
        words.add(w)
    return sorted(words, key=len, reverse=True)


def analyze(ledger: list[dict], vocab: list[str] | None = None) -> str:
    rows = [r for r in ledger if r["status"] != "test"]
    if not rows:
        return "# リクエストの分析\n\nまだ、リクエストはありません。\n"
    by_src = Counter(r["src"] for r in rows)
    by_status = Counter(r["status"] for r in rows)
    by_use = Counter(r["use"] or "(未選択)" for r in rows)
    by_touch = Counter(r["touch"] or "(未選択)" for r in rows)
    vocab = library_vocab() if vocab is None else vocab
    words = Counter()
    for r in rows:
        if r["status"] in ("declined",):
            continue
        f = flat(r["wish"][:200])
        hit = [v for v in vocab if flat(v) and flat(v) in f]
        # a longer known word hides the shorter ones inside it ("お正月" hides "正月")
        hit = [v for v in hit if not any(v != u and flat(v) in flat(u) for u in hit)]
        for v in hit:
            words[v] += 1
    why = Counter(r["auto"] for r in rows if r["auto"])
    months = Counter(r["at"][:7] for r in rows)
    out = ["# リクエストの分析", "", f"合計 {len(rows)} 件(試し送信は除く)。集計日 {date.today().isoformat()}。個人は特定できません(住所・連絡先は保存していません)。", "",
           "## 状態", "", *[f"- {k}: {v}" for k, v in sorted(by_status.items())], "",
           "## どこから来たか", "", "- form = リクエスト欄、miss = 検索で見つからなかったあとの送信、plus = 「私もほしい」、letter = くわしいフォーム", *[f"- {k}: {v}" for k, v in by_src.most_common()], "",
           "## 使い道", "", *[f"- {k}: {v}" for k, v in by_use.most_common()], "",
           "## タッチ", "", *[f"- {k}: {v}" for k, v in by_touch.most_common()], "",
           "## 言葉(多い順。サイトの企画と読みものの手がかり)", "", *[f"- {w}: {n}" for w, n in words.most_common(40)], "",
           "## 受け付けなかった理由(自動)", "", *([f"- {k}: {v}" for k, v in why.most_common()] or ["- なし"]), "",
           "## 月ごと", "", *[f"- {k}: {v}" for k, v in sorted(months.items())], ""]
    return "\n".join(out)


def cmd_analyze(a) -> int:
    GROWTH.mkdir(parents=True, exist_ok=True)
    text = analyze(read_ledger())
    (GROWTH / "ANALYSIS.md").write_text(text, encoding="utf-8")
    print(text[:1500])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("wish")
    r = sub.add_parser("read"); r.add_argument("--mark", action="store_true"); r.add_argument("--all", action="store_true")
    ls = sub.add_parser("list"); ls.add_argument("--status", default="")
    d = sub.add_parser("decide"); d.add_argument("id"); d.add_argument("decision", choices=["accepted", "declined", "merged"]); d.add_argument("--note", default="")
    s = sub.add_parser("spec"); s.add_argument("id"); s.add_argument("--title", required=True); s.add_argument("--en", required=True); s.add_argument("--slug", default="")
    s.add_argument("--touch", default="kawaii"); s.add_argument("--genre", default="animals"); s.add_argument("--subject", default="")
    p = sub.add_parser("published"); p.add_argument("id"); p.add_argument("series")
    sub.add_parser("board"); sub.add_parser("analyze")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        why, msg = refusal(a.wish)
        print("ok" if not why else f"{why}: {msg}")
        return 0
    return {"read": cmd_read, "list": cmd_list, "decide": cmd_decide, "spec": cmd_spec, "published": cmd_published, "board": cmd_board, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
