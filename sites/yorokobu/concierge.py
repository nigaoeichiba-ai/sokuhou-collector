"""贈り物コンシェルジュ: a small counter at the corner of every page that asks 「どういったことでお困りですか?」, answers by pointing to the right page of the site, and
counts (anonymously) what people ask for.

It is rules and word lists, no AI, and it runs in the browser (assets/concierge.js reads concierge-data.json, made here from the site's own content): what a visitor
types stays on the device unless the visitor presses 「送る」 on a box that says what will be done with it (api/ask.php op "voice": a line of text, no address,
no name, kept without the visitor's identity and read by the operator through the encrypted inbox).  The counters (api/ask.php op "stat", keys cq.*) are one number
per kind of question; see sites/yorokobu/askstats.py for how they are merged and read.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sokuhou.sitekit import BuildError

HERE = Path(__file__).resolve().parent
FILE = HERE / "content" / "concierge.json"
TOPICS = ("who", "what", "budget", "urgent", "manners", "sale", "other")


def load(path: Path | None = None) -> dict:
    raw = json.loads((path or FILE).read_text(encoding="utf-8"))
    for key in ("occasion_words", "recipient_words", "ambiguous_recipients", "topics", "why"):
        if key not in raw:
            raise BuildError(f"concierge.json: missing {key}")
    ids = [t.get("id") for t in raw["topics"]]
    if sorted(ids) != sorted(TOPICS):
        raise BuildError(f"concierge.json: topics have to be exactly {', '.join(TOPICS)} (the script has a branch for each)")
    for t in raw["topics"]:
        if not t.get("label") or not t.get("reply"):
            raise BuildError(f"concierge.json: topic {t.get('id')} needs a label and a reply")
    return raw


def _slugs(name: str, key: str) -> set[str]:
    return {x["slug"] for x in json.loads((HERE / "content" / name).read_text(encoding="utf-8"))[key]}


def check(raw: dict) -> None:
    """Every slug the word lists name is one of the site's (the content files, not the page set of a build: a test build has fewer pages)."""
    occ, rec = _slugs("occasions.json", "occasions"), _slugs("recipients.json", "recipients")
    for slug in raw["occasion_words"]:
        if slug not in occ:
            raise BuildError(f"concierge.json: unknown occasion {slug}")
    for slug in raw["recipient_words"]:
        if slug not in rec:
            raise BuildError(f"concierge.json: unknown recipient {slug}")
    for word, slugs in raw["ambiguous_recipients"].items():
        for s in slugs:
            if s not in rec:
                raise BuildError(f"concierge.json: {word} names an unknown recipient {s}")


def base_name(name: str) -> str:
    """'幼児(1〜5歳)' -> '幼児' (the part before a bracket, either width)."""
    return re.split(r"[(（]", name)[0]


def _words(name: str, extra: list[str]) -> list[str]:
    """The names the site gives (cut at '・' and a bracket: '就職・入社祝い' also answers to '就職') and the extra words, longest first."""
    out = {name}
    for part in re.split(r"[・(（)）]", name):
        if len(part) >= 2:
            out.add(part)
    out.update(w for w in extra if w)
    return sorted(out, key=lambda w: (-len(w), w))


def data(d: dict, cfg: dict, finder: dict) -> str:
    """concierge-data.json: what the script needs to read a sentence and to name the page it leads to."""
    c, raw = d["c"], load()
    check(raw)
    live_pairs = {f"{o}-{r}": tiers for o, rr in finder.items() for r, tiers in rr.items()}
    out = {
        "occ": [{"s": o["slug"], "n": o["name"], "w": _words(o["name"], raw["occasion_words"].get(o["slug"], []))} for o in c["occasions"]],
        "rec": [{"s": r["slug"], "n": base_name(r["name"]), "w": _words(base_name(r["name"]), raw["recipient_words"].get(r["slug"], []))} for r in c["recipients"]],
        "amb": raw["ambiguous_recipients"],
        "tiers": [{"s": t["slug"], "l": t["label"], "min": t["min"], "max": t["max"]} for t in c["filters"]["tiers"]],
        "pairs": live_pairs,
        "themes": [{"s": t["slug"], "n": t["name"], "w": sorted({w for w in t.get("keywords", []) if len(w) >= 2}, key=lambda w: (-len(w), w))} for t in d.get("live_themes", [])],
        "guides": sorted(c["guides"]),
        "topics": raw["topics"],
        "why": raw["why"],
        "sale": True,
        "aff": {"id": cfg.get("rakuten_affiliate_id", ""), "trk": cfg.get("rakuten_tracking_id") or ""},
    }
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


PRIVACY = ("<h2>贈り物コンシェルジュ</h2>"
           "<p>各ページの左下の「贈り物の相談」では、お困りのことを選ぶか、文章で書くと合うページをご案内します。案内はお使いのブラウザの中で行い、書いた文章は送りません。"
           "どんな相談が選ばれたか(「予算の目安を知りたい」「母の日」「彼女」など)は、種類ごとの回数だけを数えます。押した人、ブラウザ、IPアドレス、時刻は記録しません。"
           "ブラウザの「トラッキングしない」設定がオンのときは、数えません。</p>"
           "<p>「送る」を押した文章だけは、サイトの改善のために当サイトのサーバーに保存します。名前・連絡先・住所などは書かないでください"
           "(電話番号・メールアドレス・住所・リンクのように見える文章は、受け付けません)。保存した文章は運営者だけが読み、第三者へ提供しません。送られた文章をサイトの改善に使います。</p>")
