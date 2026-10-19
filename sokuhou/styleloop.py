"""styleloop: keep the Japanese of the sites natural by itself, a little better every day (owner's order, 2026-10-17: do not stop a publish, fix the sentence).

    python -m sokuhou.styleloop extract <built-dir|site> [--site NAME]   # the short texts (headings, buttons, links, labels, title, descriptions, alt ...), once each
    python -m sokuhou.styleloop flags   <built-dir|site> [--site NAME]   # the ones the rules already find suspicious
    python -m sokuhou.styleloop judge   <built-dir|site> [--site NAME] [--batches 3] [--accept]   # ask Codex (read-only) which are unnatural and for a rewording
    python -m sokuhou.styleloop add --site NAME --from "原文" --to "直した文" [--by owner] [--why ...]   # an owner's correction goes in the dictionary at once
    python -m sokuhou.styleloop apply   <built-dir> --site NAME          # the rewrite dictionary, applied to the built HTML (deterministic; run after the build)
    python -m sokuhou.styleloop source  --site NAME [--dry] | revert     # put the rewording into sites/<name>/ where the old text stands verbatim (backup; the keeper runs the tests)
    python -m sokuhou.styleloop learn                                    # kinds of rewording that came up three times: candidates for a rule
    python -m sokuhou.styleloop report --site NAME [--since 2026-10-17]  # before → after, for the report to the desk

Data (all in the repository, no personal data): data/style/examples.json (owner corrections = the judge's models), data/style/rewrites/<site>.json (the dictionary: exact
original → rewording), data/style/judged/<site>.json (what the judge said, so an unchanged text is not asked twice), data/style/learned_rules.json (promoted patterns).
Design: sokuhou-sites/docs/STYLE_AUTOFIX_DESIGN.md.  Nothing is changed unless it passes `check_rewrite` (numbers, names, links, length, the site's own rules).
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from sokuhou import lexicon
from sokuhou import naturaljp as nj

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "style"
CODEX_MODEL = "gpt-5.6-sol"
BATCH = 60

# --------------------------------------------------------------------------------------------------------------------------------- the short texts
HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
LABELS = {"label", "legend", "caption", "th", "summary", "figcaption", "button", "option"}
SKIP = {"script", "style", "noscript", "svg", "template", "code", "pre", "textarea", "blockquote", "cite", "select"}
ATTRS = ("alt", "aria-label", "placeholder", "title")
MAX_SHORT = 80


@dataclass
class Unit:
    kind: str                 # heading | button | link | nav | label | title | description | alt | aria | placeholder
    text: str
    pages: int = 0
    example: str = ""         # a page that shows it
    kinds: set = field(default_factory=set)
    current: str = ""         # a rewording already in the dictionary (a re-check asks whether it is the best one)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


class _Short(HTMLParser):
    """The short texts of one page: [(kind, text)].  An element counts only when its text is ONE text node (so a rewording can replace it exactly)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[tuple[str, str]] = []
        self.stack: list[tuple[str, list[str]]] = []         # (tag, text nodes seen inside)
        self.skip = 0
        self.in_title = False
        self.title: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key in ("description", "og:title", "og:description", "twitter:title", "twitter:description") and a.get("content"):
                self.out.append(("description" if "description" in key else "title", norm(a["content"])))
            return
        if tag in SKIP:
            self.skip += 1
        if tag == "title":
            self.in_title = True
            self.title = []
        if not self.skip:
            for k in ATTRS:
                if a.get(k) and tag in ("img", "input", "a", "button", "textarea", "area", "svg", "div", "span", "nav", "section", "form", "select", "iframe"):
                    self.out.append(({"alt": "alt", "aria-label": "aria", "placeholder": "placeholder", "title": "aria"}[k], norm(a[k])))
            if tag == "input" and (a.get("type") or "").lower() in ("button", "submit") and a.get("value"):
                self.out.append(("button", norm(a["value"])))
        if tag not in ("br", "hr", "img", "input", "link", "meta", "area", "wbr"):
            self.stack.append((tag, []))

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False
            t = norm("".join(self.title))
            if t:
                self.out.append(("title", t))
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                _, nodes = self.stack[i]
                del self.stack[i:]
                nodes = [n for n in nodes if n.strip()]
                if len(nodes) == 1 and not self.skip:
                    t = norm(nodes[0])
                    kind = "heading" if tag in HEAD else ("button" if tag == "button" else ("link" if tag == "a" else ("label" if tag in LABELS else None)))
                    if kind == "link" and any(s[0] in ("nav", "header", "footer") for s in self.stack):
                        kind = "nav"
                    if kind and t and len(t) <= MAX_SHORT and re.search(rf"[{nj.JP}]", t):
                        self.out.append((kind, t))
                break

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.skip:
            return
        for _, nodes in self.stack:
            nodes.append(data)


def page_units(raw: str) -> list[tuple[str, str]]:
    p = _Short()
    p.feed(raw)
    return [(k, t) for k, t in p.out if t and re.search(rf"[{nj.JP}]", t)]


def sentence_units(root: Path, site: str | None = None, max_len: int = 160) -> dict[str, Unit]:
    """The body sentences that naturaljp finds suspicious (mid and high): the ones worth asking the judge about.  A paragraph-wide finding is not a sentence and is left out."""
    hits, _ = nj.check_path(root, site, (".html", ".htm"), min_level="mid")
    units: dict[str, Unit] = {}
    for h in hits:
        t = norm(h.full or h.sentence)
        if not t or t.endswith("…") or len(t) > max_len or not t.endswith(("。", "！", "？")):
            continue
        u = units.setdefault(t, Unit("sentence", t, 0, h.path, {"sentence"}))
        u.pages += 1
    return units


def extract_units(root: Path, site: str | None = None) -> dict[str, Unit]:
    units: dict[str, Unit] = {}
    for f in nj.walk_files(root, (".html", ".htm")):
        rel = str(f.relative_to(root)).replace("\\", "/")
        if nj.EXEMPT_PATH.search(rel):
            continue
        try:
            raw = nj.for_reading(nj.published_text(f.read_text(encoding="utf-8"), site), site)         # what is published (the dictionary applied), without the shops' data
        except (OSError, UnicodeDecodeError):
            continue
        seen = set()
        for kind, text in page_units(raw):
            u = units.get(text)
            if u is None:
                u = units[text] = Unit(kind, text, 0, rel)
            u.kinds.add(kind)
            if text not in seen:
                seen.add(text)
                u.pages += 1
    return units


# --------------------------------------------------------------------------------------------------------------------------------- what the rules find in a short text
HEAVY = [
    ("heavy_compound", r"掘り下げ|切り口|紐解|俯瞰|網羅的|体系的|包括的|担保|観点から|側面から|枠組み|昨今|(?:価格|仕様|金額|予算|相場)の位置|基軸|ご査収|ご査証",
     "堅い複合語・内輪の編集語。ふつうの人はこう言わない"),
    ("kanren", r"に関する|に係る|にかかる|に際して|に伴う|について(?:のご案内|のお知らせ|のご紹介)", "法令文・お役所の言い回し"),
    ("heading_ends_nitsuite", r"について$", "「〜について」で終わる見出し・ボタンは、何が分かるのかを言っていない"),
    ("coined_label", r"ソムリエ|ナビゲーター|見立て|ギフトマップ|ガチャ|コンシェルジュ|ナレッジ|ソリューション", "内輪の語・取って付けたような外来語"),
    ("noun_pile_heading", r"^(?:[^のはがをにでと、。]+の){3,}[^の、。]+$", "名詞を「の」でつないだだけの見出し"),
    ("child_tone", r"て(?:ね|くださいね)[。！!]?$|だよ[。！!]?$|しよう[。！!]?$", "子どもに話しかける口調"),
    ("person_phrase", r"[^、。\s]{1,10}(?:を|に)?(?:開いた|開いてくれた|してくれた|くれた|くださった|手伝ってくれた|招いた|呼んだ|迎えた|企画した|用意した|世話をした|世話してくれた)人",
     "人を説明で指している(〜を開いた人)。幹事・主催者・まとめ役・世話役・ホスト・担当者のような役割の名前で言えないか"),
    ("bare_noun", r"(?:贈る|渡す|添える|届ける|返す|選ぶ)(?:お礼|お返し|感謝|気持ち|対応|サポート)$|^(?:お礼|対応|サポート|お返し)$",
     "単独の抽象名詞。何を指すか分からない(お礼の品・お礼状・お礼の言葉・お礼の金額のどれか)"),
    ("verb_modifies_noun", r"(?:労う|ねぎらう|気遣う|もてなす|励ます|喜ばせる)(?:贈り方|選び方|方法|渡し方|やり方|ギフト)",
     "動詞が名詞(贈り方)にかかる言い方。何が何をするかが分かる形に(〜への、〜の品)"),
    ("mechanical_phrase", r"詳細はこちら$|こちらをご覧ください$|ご確認ください$|をご紹介します?$|を解説します?$|について解説$", "どのサイトにもある定型の案内文"),
]
_HEAVY = [(rid, re.compile(p), why) for rid, p, why in HEAVY]


def learned_rules() -> list[tuple[str, re.Pattern, str]]:
    f = DATA / "learned_rules.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return [(r["id"], re.compile(r["pattern"]), r.get("why", "")) for r in d.get("rules", [])]


def short_flags(u: Unit, site: str | None = None) -> list[tuple[str, str]]:
    out = []
    for rid, pat, why in _HEAVY + learned_rules():
        if pat.search(u.text):
            out.append((rid, why))
    if len(u.text) > 20:                                           # a longer text: the sentence rules of naturaljp too
        out += [(h.rule, nj.RULES[h.rule].why) for h in nj.check_text(u.text, site, min_level="mid")]
    return out


# --------------------------------------------------------------------------------------------------------------------------------- invariants: what a rewording may not change
KANJI_NUM = re.compile(r"[一二三四五六七八九十百千万億]+")
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9&'.+\-]*")
KATAKANA = re.compile(r"[ァ-ヴー]{3,}")
QUOTED = re.compile(r"[「『][^」』]+[」』]")
NEW_CLAIMS = ("人気", "よく読まれ", "売れて", "定番", "喜ばれ", "試し", "使ってみ", "実際に使", "検証", "保証", "必ず", "最安", "No.1", "日本一", "絶対", "医師", "専門家", "1位", "一位")
EMOJI = re.compile("[\U0001F300-\U0001FAFF✨❗]")
ALLOW_DROP = {"ソムリエ", "ナビゲーター", "ギフトマップ", "ガチャ", "コンシェルジュ", "ナレッジ", "ソリューション"}     # coined words the owner or the style guide asked to replace


IDIOM_NUM = re.compile(r"一文|一行|一字|一通り|一言|一歩|一番|一緒|一方|一部|一般|一度|一覧|一目|一切|唯一|万一|統一|同一|一体|一致|一時|一つ|ひとつ|十分|一律|一定|一斉|一括|一新|万全|千差万別")


def digits(s: str) -> list[str]:
    s = unicodedata.normalize("NFKC", s)
    return re.findall(r"\d+(?:[.,]\d+)*", s) + KANJI_NUM.findall(IDIOM_NUM.sub("", s))      # kanji numerals count, but not those inside everyday words (一言・一歩・十分)


# General katakana words (not names, not product words): an editor may replace them (ギフトプレゼント -> 贈り物).  Brands, product materials and categories (ステンレス, タオル, レンジ) stay protected.
GENERIC_KATAKANA = ("ギフト", "プレゼント", "ポスト", "タイミング", "サイト", "ページ", "セット", "メッセージ", "カード", "マナー", "ルール", "アイテム", "ポイント", "ケース", "タイプ", "イメージ",
                    "テーマ", "メリット", "デメリット", "ニーズ", "サポート", "ソリューション", "ベネフィット", "シーン", "バランス", "ペース", "スタイル", "チェック", "リスト", "ガイド", "ポイント")
_GENERIC_RUN = re.compile("(?:" + "|".join(sorted(set(GENERIC_KATAKANA), key=len, reverse=True)) + ")+")


def protected_tokens(s: str) -> Counter:
    s2 = unicodedata.normalize("NFKC", s)
    kata = [t for t in KATAKANA.findall(s) if not _GENERIC_RUN.fullmatch(t)]
    return Counter(LATIN.findall(s2)) + Counter(kata) + Counter(QUOTED.findall(s))


def hira_ratio(s: str) -> float:
    jp = re.findall(rf"[{nj.JP}]", s)
    return sum(1 for c in jp if "ぁ" <= c <= "ん") / len(jp) if jp else 0.0


def added_words(old: str, new: str) -> list[str]:
    """Nouns (2+ kanji or katakana) of the new text that the old text does not contain at all (judged: adding or dropping a word changes what the text says)."""
    o = unicodedata.normalize("NFKC", old)
    out = []
    for m in re.finditer(r"[ァ-ヴー]{2,}|[一-龥]{2,}", unicodedata.normalize("NFKC", new)):
        w = m.group(0)
        if w not in o and not (any(c in o for c in w) if re.match(r"[一-龥]", w) else all(c in o for c in w)):
            out.append(w)
    # a single kanji tacked on to a word (お礼 -> お礼の品)
    for m in re.finditer(r"の([一-龥])(?![一-龥])", unicodedata.normalize("NFKC", new)):
        if m.group(1) not in o:
            out.append(m.group(1))
    return out


def check_rewrite(old: str, new: str, site: str | None = None, kind: str = "heading", small_edit: bool = True, new_words: bool = True) -> list[str]:
    """Reasons a rewording is NOT accepted (empty list = accepted)."""
    bad: list[str] = []
    new = new.strip()
    if not new or new == old:
        return ["empty or unchanged"]
    if re.search(r"[<>\n]|https?:|\*\*", new):
        bad.append("markup, newline or a URL in the new text")
    if digits(old) != digits(new):
        bad.append(f"numbers differ: {digits(old)} -> {digits(new)}")
    po, pn = protected_tokens(old), protected_tokens(new)
    lost = [t for t, n in po.items() if pn[t] < n and t not in ALLOW_DROP]
    if lost:
        bad.append(f"names / quoted words lost: {lost}")
    for w in NEW_CLAIMS:
        if w in new and w not in old:
            bad.append(f"new claim: {w}")
    added = added_words(old, new) if new_words and kind in ("para", "sentence", "note", "item") else []
    if added:
        bad.append(f"words added that the original does not have (information must not grow): {added}")
    if EMOJI.search(new) or (("!" in new or "！" in new) and not ("!" in old or "！" in old)):
        bad.append("emoji or exclamation added")
    n_old, n_new = len(old), len(new)
    long_kind = kind in ("description", "note", "para", "sentence")
    if n_new > (n_old * 1.5 + 10 if long_kind else max(n_old * 2, n_old + 12)):
        bad.append(f"too much longer ({n_old} -> {n_new})")
    if n_new < n_old * 0.35 and n_old > 12:
        bad.append(f"too much shorter ({n_old} -> {n_new})")
    if small_edit and long_kind and n_old > 20 and difflib.SequenceMatcher(None, old, new).ratio() < 0.5:
        bad.append("not a small edit: the sentence was rewritten")
    back = [w for w in lexicon.owner_avoided(site) if w in new and w not in old]
    if back:
        bad.append(f"wording the owner asked us to avoid: {back}")
    # the rewording must not be unnatural by our own rules
    old_rules = {h.rule for h in nj.check_text(old, site, min_level="mid")}
    new_rules = {h.rule for h in nj.check_text(new, site, min_level="mid")} - old_rules
    if new_rules:
        bad.append(f"naturaljp finds: {sorted(new_rules)}")
    flags_new = {rid for rid, _ in short_flags(Unit(kind, new), site)} - {rid for rid, _ in short_flags(Unit(kind, old), site)}
    if flags_new:
        bad.append(f"short-text rules find: {sorted(flags_new)}")
    # the site's own rules
    if site == "yorokobu":
        try:
            from sites.yorokobu import commas
            lightened = commas.lighten_short(new) if n_new <= commas.SHORT_PHRASE else commas.lighten(new)
            if "、" in new and lightened != new:
                bad.append("yorokobu commas rule")
        except ImportError:
            pass
        if re.search(r"ね[。！]?$|よ[。！]?$", new):
            bad.append("yorokobu: childish ending")
    elif site == "atomou":
        if hira_ratio(new) > hira_ratio(old) + 0.05:
            bad.append("atomou: more hiragana")
        if re.search(r"[ぁ-んァ-ヶ一-龥] [ぁ-んァ-ヶ一-龥]", new) and not re.search(r"[ぁ-んァ-ヶ一-龥] [ぁ-んァ-ヶ一-龥]", old):
            bad.append("atomou: spaced writing")
    elif site == "minna":
        if hira_ratio(new) > hira_ratio(old) + 0.05:
            bad.append("minna: more hiragana")
        if new.count("、") > 2:
            bad.append("minna: more than two commas")
    elif site in ("kuma", "saichin"):
        if n_new > n_old * 1.3 + 6 and not long_kind:
            bad.append("data site: keep it short")
    return bad


# --------------------------------------------------------------------------------------------------------------------------------- the dictionary
def rewrites_path(site: str) -> Path:
    return DATA / "rewrites" / f"{site}.json"


def load_rewrites(site: str) -> list[dict]:
    f = rewrites_path(site)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("entries", [])
    except ValueError:
        return []


def save_rewrites(site: str, entries: list[dict]) -> None:
    f = rewrites_path(site)
    f.parent.mkdir(parents=True, exist_ok=True)
    entries = sorted(entries, key=lambda e: (e["added"], e["from"]))
    f.write_text(json.dumps({"_note": "exact original -> rewording, applied after the build by sokuhou.styleloop (delete a line to undo it)", "entries": entries}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


SHOP_URL = re.compile(r"rakuten\.co\.jp|shopping\.yahoo|image\.rakuten|thumbnail\.image|placehold|amazon\.co\.jp|amzn\.")


def add_entry(site: str, old: str, new: str, by: str = "codex", why: str = "", kind: str = "heading", force: bool = False, today: str | None = None,
              small_edit: bool = True) -> tuple[bool, list[str]]:
    old, new = norm(old), norm(new)
    if SHOP_URL.search(old) or SHOP_URL.search(new):
        return False, ["a shop's address or image is the shop's data: never stored"]
    problems = [] if force else check_rewrite(old, new, site, kind, small_edit=small_edit)
    if problems:
        return False, problems
    entries = load_rewrites(site)
    if any(e["from"] == old for e in entries):
        return False, ["already in the dictionary"]
    for e in entries:                                          # the text being edited is already the result of a dictionary line: compose (original -> newest wording)
        if norm(e["to"]) == old:
            e["prev"] = e["to"]
            e["to"] = new
            e["why"] = why or e.get("why", "")
            e["rechecked"] = today or dt.date.today().isoformat()
            save_rewrites(site, entries)
            return True, []
    entries.append({"from": old, "to": new, "kind": kind, "by": by, "why": why, "added": today or dt.date.today().isoformat(), **({"forced": True} if force else {}), **({} if small_edit else {"edit": True})})
    save_rewrites(site, entries)
    return True, []


class Rewriter:
    """Applies the dictionary to a page's HTML: whole text nodes and attribute values by exact match; a long original (12+ characters) also inside a longer text."""

    def __init__(self, entries: list[dict]):
        self.exact = {norm(e["from"]): e["to"] for e in entries}
        self.long = {k: v for k, v in self.exact.items() if len(k) >= 12}
        self.index: dict[str, list[str]] = {}
        for k in sorted(self.long, key=len, reverse=True):
            self.index.setdefault(k[:8], []).append(k)
        self.hits: Counter = Counter()

    def text(self, seg: str) -> str:
        if not seg.strip():
            return seg
        plain = html.unescape(seg)
        key = norm(plain)
        if key in self.exact:
            self.hits[key] += 1
            lead = re.match(r"\s*", seg).group(0)
            trail = re.search(r"\s*$", seg).group(0)
            return lead + html.escape(self.exact[key], quote=False) + trail
        if self.index and len(plain) >= 12:
            out, i, changed = [], 0, False
            while i < len(plain):
                for k in self.index.get(plain[i:i + 8], ()) if i + 8 <= len(plain) else ():
                    if plain.startswith(k, i):
                        self.hits[k] += 1
                        out.append(self.long[k])
                        i += len(k)
                        changed = True
                        break
                else:
                    out.append(plain[i])
                    i += 1
            if changed:
                return html.escape("".join(out), quote=False)
        return seg

    def attr(self, value: str) -> str:
        key = norm(value)
        if key in self.exact:
            self.hits[key] += 1
            return html.escape(self.exact[key], quote=True)
        return value

    def page(self, raw: str) -> str:
        parts = re.split(r"(<[^>]*>)", raw)
        out, skip = [], 0
        for p in parts:
            if p.startswith("<") and p.endswith(">"):
                m = re.match(r"<(/?)([a-zA-Z0-9]+)", p)
                if m:
                    name = m.group(2).lower()
                    if name in SKIP:
                        skip += -1 if m.group(1) else 1
                        skip = max(skip, 0)
                    if not m.group(1):
                        p = self.tag(p, name)
                out.append(p)
            else:
                out.append(p if skip else self.text(p))
        return "".join(out)

    def tag(self, tag: str, name: str) -> str:
        meta_ok = name == "meta" and re.search(r'(?:name|property)=["\'](?:description|og:title|og:description|twitter:title|twitter:description)["\']', tag, re.I)
        def sub(m):
            attr = m.group(1).lower()
            if attr in ATTRS or (attr == "content" and meta_ok) or (attr == "value" and re.search(r'type=["\'](?:button|submit)["\']', tag, re.I)):
                return f'{m.group(1)}={m.group(2)}{self.attr(m.group(3))}{m.group(2)}'
            return m.group(0)
        return re.sub(r'([a-zA-Z\-]+)=(["\'])(.*?)\2', sub, tag)


TAGS = re.compile(r"<(/?[a-zA-Z][a-zA-Z0-9]*)")
HREFS = re.compile(r"""(?:href|src|action)=["'][^"']*["']""")


def usable_entries(site: str, warn=print) -> tuple[list[dict], int]:
    """The dictionary lines that may be applied NOW: every line is checked again against the rules of today (numbers, names, claims, the site's rules), so a line that was
    fine when it was written and is not any more (a rule got stricter) is left out.  An owner's own correction (forced) is applied as written."""
    f = rewrites_path(site)
    if f.exists():
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            warn(f"the dictionary of {site} is not valid JSON ({e}): nothing is applied")
            return [], 0
    ok, skipped = [], 0
    for e in load_rewrites(site):
        try:
            problems = [] if e.get("forced") else check_rewrite(norm(e["from"]), norm(e["to"]), site, e.get("kind", "heading"), small_edit=not e.get("edit"), new_words=not e.get("edit"))
        except Exception as ex:                                        # a bug in a check must not stop a publish
            problems = [f"check failed: {ex}"]
        if problems:
            skipped += 1
            warn(f"a dictionary line of {site} is not applied ({'; '.join(problems)[:120]})")
        else:
            ok.append(e)
    return ok, skipped


def apply_dir(root: Path, site: str, dry: bool = False, warn=print) -> Counter:
    """Rewrite the built HTML with the dictionary.  Fails open: whatever goes wrong with a line, a file or the whole dictionary, the page keeps its own text."""
    stats: Counter = Counter()
    entries, skipped = usable_entries(site, warn)
    stats["entries"] = len(entries) + skipped
    stats["skipped_entries"] = skipped
    if not entries:
        return stats
    rw = Rewriter(entries)
    for f in nj.walk_files(root, (".html", ".htm")):
        rel = str(f.relative_to(root)).replace("\\", "/")
        if nj.EXEMPT_PATH.search(rel):
            continue
        try:
            raw = f.read_text(encoding="utf-8")
            snapshot = Counter(rw.hits)
            before = sum(rw.hits.values())
            new = rw.page(raw)
            if new == raw:
                continue
            if TAGS.findall(raw) != TAGS.findall(new) or HREFS.findall(raw) != HREFS.findall(new):         # a rewording may never change the markup or a link
                warn(f"{rel}: the markup or a link would change; the page is left as it is")
                stats["skipped_files"] += 1
                rw.hits = snapshot
                continue
            stats["pages"] += 1
            stats["replacements"] += sum(rw.hits.values()) - before
            if not dry:
                f.write_text(new, encoding="utf-8", newline="")
        except Exception as ex:
            warn(f"{rel}: not rewritten ({ex})")
            stats["skipped_files"] += 1
    stats["texts"] = len(rw.hits)
    return stats


# --------------------------------------------------------------------------------------------------------------------------------- the judge (Codex, read-only)
def examples() -> list[dict]:
    f = DATA / "examples.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("examples", [])
    except (OSError, ValueError):
        return []


SITE_STYLE = {
    "yorokobu": "大人が落ち着いて贈り物を選ぶサイト。です・ます。親しげな口調(〜ね・〜よ)、内輪の語、試したという体験は不可。読点は意味の切れ目だけで、元より増やさない(短い文には打たない)。",
    "minna": "プロ(Web・出版・広告の制作者)と、年賀状などを自分で作る大人向けの素材サイト。ふつうの日本語。漢字にできる語は漢字に。読点は少なく。",
    "atomou": "あと何日・もう何日を数えるアプリ。中学生以上が読む。ひらがなを増やさない。分かち書きしない。",
    "kuma": "クマ出没情報のデータサイト。事実を短く。",
    "saichin": "最低賃金のデータサイト。事実を短く。",
}


def principles() -> list[str]:
    try:
        return json.loads((DATA / "examples.json").read_text(encoding="utf-8")).get("principles", [])
    except (OSError, ValueError):
        return []


def judge_prompt(site: str, batch: list[Unit]) -> str:
    ex = [e for e in examples()]
    ex_txt = "\n".join(f"- 「{e['before']}」→「{e['after']}」({e['site']}・{e['kind']}。{e.get('why', '')})" for e in ex)
    items = [{"id": i + 1, "kind": u.kind, "text": u.text, **({"current": u.current} if u.current else {})} for i, u in enumerate(batch)]
    pr = chr(10).join(f"{i}. {p}" for i, p in enumerate(principles(), 1))
    ref = lexicon.reference(site)
    ref_txt = (f'''実際によく使われる言い方(大手EC・百貨店・文章のプロの実物から作った辞書。理屈で作った言い換え表ではない。「弱=決め手にしない」の語は参考だけにする):
{ref}
''' if ref else "")
    return f"""あなたは日本語の校閲者です。次の「短い言葉」(見出し・ボタン・ラベル・メニュー・タイトル・説明文・代替テキスト)が、日本語のサイトの文言として自然かを一つずつ判定してください。
サイト: {site}。{SITE_STYLE.get(site, '')}
基準: ふつうの人がその場面で自然に言うか。堅い複合語(掘り下げる・〜の位置)、翻訳調、お役所の言い回し、内輪の編集語、名詞をつないだだけの見出し、AIが作ったような決まり文句は不自然。短く、ふつうの言葉で。自然なら直さない(自然なものを無理に変えない)。
オーナーが実際に直した例(必ず見本にすること):
{ex_txt}
{ref_txt}語の選び方の基本(オーナーの指示。文法より前に、基本の自然な語を選ぶ):
{pr}
見るところ: (a) 人を説明で言っていないか(〜を開いた人、〜してくれた人)。役割の名前に替えられないか。(b) 単独の抽象名詞(お礼・贈り物・対応・サポート)が、何を指すか曖昧でないか。(c) 名詞を動詞にかける言い方や、名詞だけの連なりでないか。
直すのは不自然な部分だけ。自然な語や言い回しは残し、できるだけ少ない変更にする(全体を書き換えない)。
守ること: 意味・事実・数字・日付・固有名(作品名・商品名・店名・イベント名・人名・地名)・「」の引用・英字・カタカナの名前は変えない。新しい主張や体験(試した・必ず・最安など)を足さない。言葉を足したり削ったりして情報を増減させる直し(例: お礼→お礼の品、あたたかい夜→あたたかなクリスマス)は不可。直し案は元の言葉と同じ程度の長さにする。
直し案の作り方: 最初に思いついた1案で決めない。同じ意味で言い方の違う候補を3つ以上考え(item に current があれば、それも候補の1つに入れる)、その中から、上の辞書にある言い方(実物で確かめてあるもの)を優先して選ぶ。辞書にない言い方を使うときは、ふつうに使われているか自分で確かめられる範囲で選び、why に書く。各候補に key(その候補の特徴が出る、検索で打つような短い語句。例「幹事 お礼 品」)を付ける。
出力: JSONだけ(前後に説明を書かない)。形式: {{"items":[{{"id":1,"natural":true,"candidates":[{{"text":"","key":""}}],"choice":1,"why":"","confidence":""}}]}}。natural が false のときだけ candidates(3つ以上)・choice(選んだ候補の番号)・why(選んだ理由を一言)・confidence("high"=誰が読んでも不自然で、選んだ案のほうが明らかによい、"low"=好みの差)を書く。固有名・データ由来の名前、画面の読み上げ用の標準的な語(パンくず 等)は natural:true。
入力:
{json.dumps(items, ensure_ascii=False)}
"""


def verify_prompt(site: str, pairs: list[tuple[str, str]]) -> str:
    items = [{"id": i + 1, "before": a, "after": b} for i, (a, b) in enumerate(pairs)]
    return f"""あなたは日本語の校閲者です。サイト({site})の文言の直し案が、元の文言と同じ意味・同じ事実のままか、一つずつ確かめてください。
同じ意味でない例: 内容が変わる・足される・減る(数字、条件、対象、注意点、出典を含む)、別の物の言い方になる、トーンが大きく変わる、かえって不自然になる。語を言い換えただけで意味が同じなら true。
あわせて、語の選び方も見る: 人を説明で言っていないか(〜を開いた人 → 幹事・主催者などの役割の名前)、単独の抽象名詞(お礼・贈り物・対応)が何を指すか曖昧でないか、名詞を動詞にかける言い方でないか、より適切でふつうに使われる言葉がないか。
出力: JSONだけ。形式: {{"items":[{{"id":1,"same_meaning":true,"natural":true,"word_choice_ok":true,"problem":""}}]}}。same_meaning は意味が同じか、natural は直し案が自然な日本語か、word_choice_ok は語の選び方が適切か(より良い言葉があれば false にして problem に書く)。
入力:
{json.dumps(items, ensure_ascii=False)}
"""


def verify(site: str, pairs: list[tuple[str, str]], runner=None) -> dict[int, bool]:
    """A second look at the rewordings that passed the checks: same meaning AND natural.  Anything not answered is not accepted."""
    runner = runner or run_codex
    answer = parse_judgement(runner(verify_prompt(site, pairs)), len(pairs))
    return {i: bool(it.get("same_meaning")) and bool(it.get("natural", True)) and bool(it.get("word_choice_ok", True)) for i, it in answer.items()}


def run_codex(prompt: str, timeout: int = 900) -> str:
    out = DATA.parent.parent / "out" / "styleloop_codex_last.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    r = subprocess.run([shutil.which("codex") or "codex", "exec", "-m", CODEX_MODEL, "-s", "read-only", "--skip-git-repo-check", "-C", str(ROOT), "-o", str(out), "-"],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"codex failed (exit {r.returncode}): {(r.stdout + r.stderr)[-300:]}")
    return out.read_text(encoding="utf-8")


def parse_judgement(text: str, n: int) -> dict[int, dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in the answer")
    d = json.loads(m.group(0))
    got = {}
    for it in d.get("items", []):
        if isinstance(it, dict) and isinstance(it.get("id"), int) and 1 <= it["id"] <= n:
            got[it["id"]] = it
    return got


def judged_path(site: str) -> Path:
    return DATA / "judged" / f"{site}.json"


def load_judged(site: str) -> dict:
    f = judged_path(site)
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_judged(site: str, d: dict) -> None:
    f = judged_path(site)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")


def key_of(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def priority(u: Unit, site: str | None) -> tuple:
    flagged = bool(short_flags(u, site))
    chrome = u.pages >= 3 or u.kinds & {"button", "nav", "title", "description"}
    return (not flagged, not chrome, -u.pages, u.text)


def pending_units(units: dict[str, Unit], site: str, judged: dict) -> list[Unit]:
    todo = [u for u in units.values() if key_of(u.text) not in judged and not protected_name(u.text)]
    return sorted(todo, key=lambda u: priority(u, site))


def protected_name(text: str) -> bool:
    """A date-led proper name or a pure code / number is not worth asking about."""
    if text.endswith("…") or text.count(" ") >= 3:                     # a cut-off product name (a shop's listing title), not the site's own words
        return True
    return not re.search(rf"[ぁ-ん{nj.KANJI}]", text) or bool(re.match(r"^[\d\s.,:/\-年月日()（）]+$", text))


SUGGEST_CACHE = "suggest_cache.json"


def fetch_suggest(query: str) -> list[str]:
    """Google's search suggestions for a phrase (public, no key).  What people type is the nearest thing to 'which wording is in use' that can be measured here."""
    import urllib.parse
    import urllib.request
    url = "https://www.google.com/complete/search?client=firefox&hl=ja&q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    return [x for x in data[1] if isinstance(x, str)]


def suggest_score(key: str, fetch=None, today: str | None = None) -> int | None:
    """How many suggestions the phrase gets, plus one for each that starts with it (1-20).  None = no evidence (no network, empty key, or nobody types a phrase this specific).  Cached in data/style/."""
    key = norm(key)
    if not key:
        return None
    cache_file = DATA / SUGGEST_CACHE
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if key in cache:
        return cache[key][0] or None
    try:
        sug = (fetch or fetch_suggest)(key)
    except Exception:
        return None
    score = len(sug) + sum(1 for x in sug if x.startswith(key))
    cache[key] = [score, today or dt.date.today().isoformat()]
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True) + chr(10), encoding="utf-8")
    return score or None                                           # no suggestion at all says nothing (a long phrase nobody types as it is): not a zero


def choose(site: str, u: Unit, it: dict, scorer=None) -> tuple[str | None, list[dict], list[str]]:
    """From the judge's candidates (3 or more asked for): the ones that pass the checks, then the one people actually use (suggestions), else the judge's own choice.
    Returns (chosen text or None, all candidates with their score/problems, the reasons the first was refused when none passed)."""
    raw = it.get("candidates")
    if not raw and (it.get("better") or "").strip():
        raw = [{"text": it["better"], "key": ""}]
    cands = []
    for c in raw or []:
        if isinstance(c, dict) and (c.get("text") or "").strip():
            cands.append({"text": norm(c["text"]), "key": norm(c.get("key") or "")})
    if not cands:
        return None, [], ["no candidates"]
    first = it.get("choice") if isinstance(it.get("choice"), int) and 1 <= it["choice"] <= len(cands) else 1
    order = [cands[first - 1]] + [c for i, c in enumerate(cands, 1) if i != first]
    problems_first: list[str] = []
    passing = []
    for c in order:
        probs = check_rewrite(u.text, c["text"], site, u.kind)
        c["problems"] = probs
        if probs:
            problems_first = problems_first or probs
        else:
            passing.append(c)
    if not passing:
        return None, order, problems_first
    for c in passing:
        c["lex"] = lexicon.support(site, c["text"])
    top = max(c["lex"] for c in passing)
    if len({c["lex"] for c in passing}) > 1:                                  # the wording the real texts use wins over one they do not
        passing = [c for c in passing if c["lex"] == top]
    for c in passing:
        c["score"] = scorer(c["key"]) if scorer and c["key"] else None
    measured = [c for c in passing if c.get("score") is not None]
    best = max(measured, key=lambda c: c["score"]) if len(measured) >= 2 and len({c["score"] for c in measured}) > 1 else passing[0]
    return best["text"], order, []


def evidence(cands: list[dict]) -> str:
    if len(cands) < 2:
        return "候補が1つだけ(語の使われ方は比べていない)"
    parts = []
    for c in cands:
        sc = c.get("score")
        lex = c.get("lex")
        parts.append(f"{c['text'][:24]}({'×' if c.get('problems') else ('辞書' + format(lex, '+d') if lex else '辞書に根拠なし')}{'' if sc is None else ',サジェスト' + str(sc)})")
    return "候補(実物の辞書での根拠): " + " / ".join(parts)


def judge(units: dict[str, Unit], site: str, batches: int = 3, accept: bool = False, runner=run_codex, today: str | None = None, verifier=None,
          scorer=None, force: bool = False, replace: bool = False) -> dict:
    """Ask about the texts not asked before (force: ask again about these units; replace: a better wording than the dictionary line replaces it)."""
    today = today or dt.date.today().isoformat()
    judged = load_judged(site)
    stats = Counter()
    todo = sorted(units.values(), key=lambda u: priority(u, site)) if force else pending_units(units, site, judged)
    for b in range(batches):
        batch = todo[b * BATCH:(b + 1) * BATCH]
        if not batch:
            break
        try:
            answer = parse_judgement(runner(judge_prompt(site, batch)), len(batch))
        except Exception as e:                                   # never "no problem" when the judge did not answer
            stats["failed_batches"] += 1
            stats["error"] = str(e)[:200]
            break
        candidates: list[tuple[Unit, dict, dict]] = []
        for i, u in enumerate(batch, 1):
            it = answer.get(i)
            if it is None:
                stats["unanswered"] += 1
                continue
            if it.get("natural", True) and not u.current:
                judged[key_of(u.text)] = {"text": u.text, "natural": True, "at": today}
                stats["natural"] += 1
                continue
            text, cands, problems = choose(site, u, it, scorer)
            rec = {"text": u.text, "natural": False, "at": today, "kind": u.kind, "confidence": str(it.get("confidence", "")),
                   "candidates": [{k: v for k, v in c.items() if k in ("text", "key", "score", "lex", "problems")} for c in cands]}
            if text is None:
                rec.update(better=cands[0]["text"] if cands else "", why=it.get("why", ""), status="rejected", problems=problems or ["no usable candidate"])
                stats["rejected"] += 1
            else:
                rec.update(better=text, why=((it.get("why", "") + " / " if it.get("why") else "") + evidence(cands)).strip())
                if u.current and text == norm(u.current):
                    rec["status"] = "kept"
                    stats["kept"] += 1
                elif accept and rec["confidence"].lower() == "high":
                    candidates.append((u, rec, it))
                else:
                    rec["status"] = "proposed"
                    stats["proposed"] += 1
            judged[key_of(u.text)] = rec
        if candidates:
            try:
                same = verify(site, [(u.text, rec["better"]) for u, rec, _ in candidates], verifier or runner)
            except Exception as e:
                same = {}
                stats["verify_failed"] += 1
                stats["error"] = str(e)[:200]
            for i, (u, rec, it) in enumerate(candidates, 1):
                if same.get(i):
                    if replace and u.current:
                        entries = load_rewrites(site)
                        for e in entries:
                            if e["from"] == norm(u.text):
                                e["prev"] = e["to"]
                                e["to"] = rec["better"]
                                e["why"] = rec["why"]
                                e["rechecked"] = today
                        save_rewrites(site, entries)
                        rec["status"] = "replaced"
                        stats["replaced"] += 1
                    else:
                        ok, _ = add_entry(site, u.text, rec["better"], by="codex", why=rec["why"], kind=u.kind, today=today)
                        rec["status"] = "accepted" if ok else "duplicate"
                        stats["accepted" if ok else "duplicate"] += 1
                else:
                    rec["status"] = "proposed"
                    rec["problems"] = ["not confirmed by the second look (meaning, naturalness or word choice)"]
                    stats["proposed"] += 1
        save_judged(site, judged)
    stats["pending_after"] = max(0, len(todo) - batches * BATCH)
    return dict(stats)


def rejudge_units(site: str, scope: str) -> dict[str, Unit]:
    """The units of a re-check: every line of the dictionary (is its rewording the best one?) or every held proposal (is there a good rewording now?)."""
    units: dict[str, Unit] = {}
    if scope == "dictionary":
        for e in load_rewrites(site):
            units[e["from"]] = Unit(e.get("kind", "heading"), e["from"], 0, "", {e.get("kind", "heading")}, current=e["to"])
    else:
        for rec in load_judged(site).values():
            if not rec.get("natural", True) and rec.get("status") in ("proposed", "rejected"):
                units[rec["text"]] = Unit(rec.get("kind", "heading"), rec["text"], 0, "", {rec.get("kind", "heading")})
    return units


# --------------------------------------------------------------------------------------------------------------------------------- the source (sites/<name>/)
# The source of the page text is DATA and CONTENT (json / md / txt in the site's content folders), never code: a string inside a .py / .js / template is a label that tests,
# other pages and the build rely on (2026-10-19: a run over .py and .json changed 21 places and broke 16 tests).
SRC_EXT = {".json", ".md", ".txt"}
SRC_DENY_NAMES = {"config.json", "package.json", "lastmod_static.json", "links.json"}
SRC_DENY_DIRS = {"__pycache__", "dist", "release", "assets", "assets_retired", "node_modules", "tests", "fixtures", "templates"}


def source_files(site: str) -> list[Path]:
    base = ROOT / "sites" / site
    return [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SRC_EXT and p.name not in SRC_DENY_NAMES and not (SRC_DENY_DIRS & set(p.relative_to(base).parts))]


# JSON keys whose values are not page text: search words, addresses, ids, tags ... (a rewording of a search query would change what the page does)
SRC_DENY_KEYS = {"query", "queries", "q", "slug", "url", "href", "src", "img", "image", "id", "code", "ref", "key", "keys", "tag", "tags", "type", "kind", "class", "k", "match", "pattern",
                 "regex", "needle", "alias", "aliases", "path", "file", "icon", "color", "lang", "date", "added", "verified"}


def _under_denied_key(raw: str, old: str) -> bool:
    """True when the text stands as the value of a key that is not page text (in this file): the entry is then left to the dictionary alone."""
    try:
        data = json.loads(raw)
    except ValueError:
        return True

    def walk(o, key):
        if isinstance(o, str):
            return key in SRC_DENY_KEYS and old in o
        if isinstance(o, dict):
            return any(walk(v, k) for k, v in o.items())
        if isinstance(o, list):
            return any(walk(v, key) for v in o)
        return False
    return walk(data, "")


def _short_pattern(old: str, is_json: bool) -> re.Pattern:
    o = re.escape(old)
    if is_json:                                              # a whole string VALUE: not followed by a colon (that would be a key)
        return re.compile(rf'(?<=["\[,:])\s*"{o}"(?!\s*:)')
    return re.compile(rf'(?<![^\s>"\'「])({o})(?![^\s<"\'」])')


def _count(raw: str, old: str, is_json: bool) -> int:
    if is_json and _under_denied_key(raw, old):
        return 0
    if len(old) >= 12:
        return raw.count(old)
    return len(_short_pattern(old, is_json).findall(raw)) if is_json else sum(raw.count(f"{q}{old}{r}") for q, r in (('"', '"'), ("'", "'"), (">", "<")))


def _replace(raw: str, old: str, new: str, is_json: bool) -> str:
    if len(old) >= 12:
        return raw.replace(old, new)
    if is_json:
        return _short_pattern(old, is_json).sub(lambda m: m.group(0).replace(f'"{old}"', f'"{new}"'), raw)
    for q, r in (('"', '"'), ("'", "'"), (">", "<")):
        raw = raw.replace(f"{q}{old}{r}", f"{q}{new}{r}")
    return raw


def source_plan(site: str) -> list[tuple[Path, str, str, int]]:
    plan = []
    entries = [e for e in load_rewrites(site) if not e.get("in_source")]
    for p in source_files(site):
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for e in entries:
            n = _count(raw, e["from"], p.suffix.lower() == ".json")
            if n:
                plan.append((p, e["from"], e["to"], n))
    return plan


def apply_source(site: str, dry: bool = False) -> list[tuple[str, str, int]]:
    plan = source_plan(site)
    backup = ROOT / "out" / "styleloop_backup" / f"{site}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    done = []
    by_file: dict[Path, list] = defaultdict(list)
    for p, old, new, n in plan:
        by_file[p].append((old, new, n))
    for p, items in by_file.items():
        raw = p.read_text(encoding="utf-8")
        is_json = p.suffix.lower() == ".json"
        new_raw = raw
        for old, new, n in items:
            new_raw = _replace(new_raw, old, new, is_json)
        if is_json:
            try:
                json.loads(new_raw)                               # a rewording with a quote or a backslash must not break the data file
            except ValueError:
                continue
        for old, new, n in items:
            done.append((str(p.relative_to(ROOT)).replace("\\", "/"), old, n))
        if not dry and new_raw != raw:
            rel = p.relative_to(ROOT)
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, backup / rel)
            p.write_text(new_raw, encoding="utf-8", newline="")
    if not dry and done:
        entries = load_rewrites(site)
        replaced = {o for _, o, _ in done}
        for e in entries:
            if e["from"] in replaced:
                e["in_source"] = True
        save_rewrites(site, entries)
        (ROOT / "out" / "styleloop_last_backup.txt").write_text(str(backup), encoding="utf-8")
    return done


def revert_source(site: str) -> int:
    ptr = ROOT / "out" / "styleloop_last_backup.txt"
    if not ptr.exists():
        return 0
    backup = Path(ptr.read_text(encoding="utf-8"))
    n = 0
    for f in backup.rglob("*"):
        if f.is_file():
            shutil.copy2(f, ROOT / f.relative_to(backup))
            n += 1
    entries = load_rewrites(site)
    for e in entries:
        e.pop("in_source", None)
    save_rewrites(site, entries)
    return n


# --------------------------------------------------------------------------------------------------------------------------------- learning
def changed_spans(old: str, new: str) -> list[tuple[str, str]]:
    sm = difflib.SequenceMatcher(None, old, new)
    return [(old[i1:i2], new[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("replace", "delete", "insert") and (i2 - i1 >= 2 or j2 - j1 >= 2)]


def learn_candidates(min_count: int = 3) -> list[tuple[str, str, int, list[str]]]:
    c: dict[tuple[str, str], list[str]] = defaultdict(list)
    for f in sorted((DATA / "rewrites").glob("*.json")) if (DATA / "rewrites").exists() else []:
        site = f.stem
        for e in load_rewrites(site):
            for span in changed_spans(e["from"], e["to"]):
                c[span].append(f"{site}:{e['from'][:20]}")
    return sorted(((a, b, len(v), v[:3]) for (a, b), v in c.items() if len(v) >= min_count), key=lambda x: -x[2])


def report(site: str, since: str = "") -> str:
    lines = []
    for e in load_rewrites(site):
        if e["added"] >= since:
            lines.append(f"- [{e['kind']}・{e['by']}・{e['added']}] 「{e['from']}」→「{e['to']}」" + (f"  — {e['why']}" if e.get("why") else "") + ("(元に反映済み)" if e.get("in_source") else ""))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------------------------------------------- command line
def resolve(target: str, site: str | None) -> tuple[Path, str | None]:
    if target in nj.SITES:
        return nj.built_dir(target), site or target
    p = Path(target)
    return p, site or nj.site_of(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="styleloop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("extract", "flags", "judge", "apply"):
        s = sub.add_parser(name)
        s.add_argument("target")
        s.add_argument("--site")
        if name == "judge":
            s.add_argument("--batches", type=int, default=3)
            s.add_argument("--accept", action="store_true", help="put the rewordings that pass the checks into the dictionary")
            s.add_argument("--suggest", action="store_true", help="also compare the candidates by search suggestions (off by default: the owner wants no one-by-one outside checks)")
            s.add_argument("--sentences", action="store_true", help="also ask about the body sentences that naturaljp finds suspicious (mid and high)")
        if name in ("extract", "flags"):
            s.add_argument("--limit", type=int, default=40)
        if name == "apply":
            s.add_argument("--dry", action="store_true")
            s.add_argument("--fail-open", action="store_true", help="never fail: a problem is a warning and the page keeps its own text (the deploy uses this)")
    a = sub.add_parser("add")
    a.add_argument("--site", required=True)
    a.add_argument("--from", dest="old", required=True)
    a.add_argument("--to", required=True)
    a.add_argument("--by", default="owner")
    a.add_argument("--why", default="")
    a.add_argument("--kind", default="heading")
    a.add_argument("--force", action="store_true", help="skip the checks (an owner's own correction)")
    c = sub.add_parser("check", help="the same checks for a rewording a person (or another session) proposes")
    c.add_argument("--site", required=True)
    c.add_argument("--from", dest="old", required=True)
    c.add_argument("--to", required=True)
    c.add_argument("--kind", default="heading")
    rj = sub.add_parser("rejudge", help="ask again: is the dictionary line the best wording / is there a good wording for a held proposal")
    rj.add_argument("--site", required=True)
    rj.add_argument("--scope", choices=["dictionary", "proposed"], default="dictionary")
    rj.add_argument("--batches", type=int, default=3)
    rj.add_argument("--accept", action="store_true")
    rj.add_argument("--suggest", action="store_true")
    e = sub.add_parser("edit", help="rewrite a whole page with one Codex call (the editor prompt); only the invariants are checked")
    e.add_argument("--site", required=True)
    e.add_argument("--page", help="a page of the built site, e.g. guide/ochugen/index.html")
    e.add_argument("--next", type=int, default=0, help="the next N pages never edited (or whose text changed)")
    e.add_argument("--build", help="a folder built WITH THE REAL DATA (default: the production site is read; a build made on this PC shows sample products and is not a safe input)")
    e.add_argument("--dry", action="store_true", help="print the prompt and change nothing")
    e.add_argument("--no-accept", action="store_true", help="check the edits and report them, but do not put them into the dictionary")
    e.add_argument("--accept", action="store_true", help="(the default) put the edits that pass every check into the dictionary")
    s = sub.add_parser("source")
    s.add_argument("--site", required=True)
    s.add_argument("--dry", action="store_true")
    s.add_argument("--revert", action="store_true")
    sub.add_parser("learn")
    r = sub.add_parser("report")
    r.add_argument("--site", required=True)
    r.add_argument("--since", default="")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "add":
        ok, why = add_entry(args.site, args.old, args.to, args.by, args.why, args.kind, args.force)
        print("added" if ok else f"not added: {why}")
        return 0 if ok else 1
    if args.cmd == "edit":
        from sokuhou import pageedit
        if args.build:
            build = Path(args.build)
            if args.page:
                pages = [(args.page, nj.published_text((build / args.page).read_text(encoding="utf-8"), args.site))]
            else:
                pages = pageedit.next_pages(args.site, build, args.next or 1)
        else:                                                    # production: the pages visitors get
            if args.site not in pageedit.LIVE:
                print(f"{args.site} has no public site to read: not measured (use --build with a folder built from real data)")
                return 1
            build = nj.built_dir(args.site)                      # only the list of page paths comes from the local build
            if args.page:
                try:
                    pages = [(args.page, pageedit.fetch_live(args.site, args.page))]
                except Exception as ex:
                    print(f"{args.page}: the production page could not be read ({ex}): not measured")
                    return 1
            else:
                pages = pageedit.next_pages(args.site, build, args.next or 1, fetch=pageedit.fetch_live)
                if not pages:
                    print("no page to edit (all edited and unchanged, or not readable on the production site)")
        failed = False
        done = pageedit.load_edited(args.site)
        for rel, raw in pages:
            rep_ = pageedit.edit_page(args.site, rel, raw, accept=not args.no_accept, dry=args.dry)
            if args.dry:
                print(rep_.get("prompt", ""))
                continue
            failed = failed or bool(rep_["failed"])
            print(f"{rel}: units {rep_['units']}, accepted {len(rep_['accepted'])}, rejected {len(rep_['rejected'])}, deleted(proposal) {len(rep_['deleted'])}, "
                  f"needs_check {len(rep_['needs_check'])}, structure {len(rep_['structure_suggestions'])}" + (f"  FAILED: {rep_['failed']}" if rep_["failed"] else ""))
            for d in rep_["diagnosis"]:
                print("  診断:", d)
            for a_ in rep_["accepted"][:8]:
                print(f"  [{a_['kind']}] 「{a_['from'][:50]}」→「{a_['to'][:50]}」 ({a_['why']})")
            for r_ in rep_["rejected"][:5]:
                print(f"  却下 「{r_['text']}」: {'; '.join(r_['problems'])[:100]}")
            if not rep_["failed"] and not args.no_accept:
                done[rel] = {k: v for k, v in rep_.items() if k != "prompt"}
                doc = pageedit.append_accepted_doc(args.site, rep_)
                if doc:
                    print(f"  → {doc.name} に前→後の表を追記")
        if not args.dry and not args.no_accept:
            pageedit.save_edited(args.site, done)
        return 1 if failed else 0
    if args.cmd == "check":
        bad = check_rewrite(norm(args.old), norm(args.to), args.site, args.kind)
        print("OK: passes every check" if not bad else "NOT accepted: " + "; ".join(bad))
        return 1 if bad else 0
    if args.cmd == "rejudge":
        st = judge(rejudge_units(args.site, args.scope), args.site, args.batches, args.accept, scorer=suggest_score if args.suggest else None,
                   force=True, replace=args.scope == "dictionary")
        print(json.dumps(st, ensure_ascii=False))
        return 1 if st.get("failed_batches") else 0
    if args.cmd == "source":
        if args.revert:
            print(f"restored {revert_source(args.site)} file(s)")
            return 0
        done = apply_source(args.site, args.dry)
        for f, old, n in done:
            print(f"{'(dry) ' if args.dry else ''}{f}: {n}× 「{old[:40]}」")
        print(f"{len(done)} place(s) in the source of {args.site}" + ("" if args.dry else "; backup: out/styleloop_last_backup.txt (run `source --revert` if the tests fail)"))
        return 0
    if args.cmd == "learn":
        c = learn_candidates()
        for old, new, n, ex in c:
            print(f"{n}×  「{old}」→「{new}」  e.g. {ex}")
        print(f"{len(c)} candidate(s) for a rule (a kind of rewording that came up 3+ times)")
        return 0
    if args.cmd == "report":
        print(report(args.site, args.since) or "(nothing)")
        return 0

    root, site = resolve(args.target, args.site)
    if args.cmd == "apply":
        def warn(msg):
            print(f"::warning::styleloop: {msg}")
        try:
            st = apply_dir(root, site or "", args.dry, warn)
        except Exception as ex:                       # fail open: the publish goes on with the original text
            warn(f"the rewrite step failed ({ex}); the site is published with its own text")
            return 0 if args.fail_open else 1
        print(f"styleloop apply site={site}: dictionary lines={st['entries']} usable={st['entries'] - st['skipped_entries']} skipped={st['skipped_entries']} "
              f"pages changed={st['pages']} replacements={st['replacements']} files left alone={st['skipped_files']}" + (" (dry run)" if args.dry else ""))
        return 0
    units = extract_units(root, site)
    if args.cmd == "extract":
        kinds = Counter(u.kind for u in units.values())
        print(f"{len(units)} short texts; by kind: {dict(kinds)}")
        for u in sorted(units.values(), key=lambda u: -u.pages)[:args.limit]:
            print(f"  [{u.kind}] ×{u.pages}  {u.text}")
        return 0
    if args.cmd == "flags":
        n = 0
        for u in sorted(units.values(), key=lambda u: -u.pages):
            fl = short_flags(u, site)
            if fl:
                n += 1
                if n <= args.limit:
                    print(f"  [{u.kind}] ×{u.pages} {u.example}  「{u.text}」 ← {', '.join(r for r, _ in fl)}")
        print(f"{n} flagged of {len(units)}")
        return 0
    if args.cmd == "judge":
        if args.sentences:
            units = {**sentence_units(root, site), **units}
        st = judge(units, site or "", args.batches, args.accept, scorer=suggest_score if args.suggest else None)
        print(json.dumps(st, ensure_ascii=False))
        return 1 if st.get("failed_batches") else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
