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
            raw = f.read_text(encoding="utf-8")
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
NEW_CLAIMS = ("試し", "使ってみ", "実際に使", "検証", "保証", "必ず", "最安", "No.1", "日本一", "絶対", "医師", "専門家", "1位", "一位")
EMOJI = re.compile("[\U0001F300-\U0001FAFF✨❗]")
ALLOW_DROP = {"ソムリエ", "ナビゲーター", "ギフトマップ", "ガチャ", "コンシェルジュ", "ナレッジ", "ソリューション"}     # coined words the owner or the style guide asked to replace


IDIOM_NUM = re.compile(r"一言|一歩|一番|一緒|一方|一部|一般|一度|一覧|一目|一切|唯一|万一|統一|同一|一体|一致|一時|一つ|ひとつ|十分|一律|一定|一斉|一括|一新|万全|千差万別")


def digits(s: str) -> list[str]:
    s = unicodedata.normalize("NFKC", s)
    return re.findall(r"\d+(?:[.,]\d+)*", s) + KANJI_NUM.findall(IDIOM_NUM.sub("", s))      # kanji numerals count, but not those inside everyday words (一言・一歩・十分)


def protected_tokens(s: str) -> Counter:
    s2 = unicodedata.normalize("NFKC", s)
    return Counter(LATIN.findall(s2)) + Counter(KATAKANA.findall(s)) + Counter(QUOTED.findall(s))


def hira_ratio(s: str) -> float:
    jp = re.findall(rf"[{nj.JP}]", s)
    return sum(1 for c in jp if "ぁ" <= c <= "ん") / len(jp) if jp else 0.0


def check_rewrite(old: str, new: str, site: str | None = None, kind: str = "heading") -> list[str]:
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
    if EMOJI.search(new) or (("!" in new or "！" in new) and not ("!" in old or "！" in old)):
        bad.append("emoji or exclamation added")
    n_old, n_new = len(old), len(new)
    long_kind = kind in ("description", "note", "para", "sentence")
    if n_new > (n_old * 1.5 + 10 if long_kind else max(n_old * 2, n_old + 12)):
        bad.append(f"too much longer ({n_old} -> {n_new})")
    if n_new < n_old * 0.35 and n_old > 12:
        bad.append(f"too much shorter ({n_old} -> {n_new})")
    if long_kind and n_old > 20 and difflib.SequenceMatcher(None, old, new).ratio() < 0.5:
        bad.append("not a small edit: the sentence was rewritten")
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


def add_entry(site: str, old: str, new: str, by: str = "codex", why: str = "", kind: str = "heading", force: bool = False, today: str | None = None) -> tuple[bool, list[str]]:
    old, new = norm(old), norm(new)
    problems = [] if force else check_rewrite(old, new, site, kind)
    if problems:
        return False, problems
    entries = load_rewrites(site)
    if any(e["from"] == old for e in entries):
        return False, ["already in the dictionary"]
    entries.append({"from": old, "to": new, "kind": kind, "by": by, "why": why, "added": today or dt.date.today().isoformat()})
    save_rewrites(site, entries)
    return True, []


class Rewriter:
    """Applies the dictionary to a page's HTML: whole text nodes and attribute values by exact match; a long original (12+ characters) also inside a longer text."""

    def __init__(self, entries: list[dict]):
        self.exact = {norm(e["from"]): e["to"] for e in entries}
        long_ = {k: v for k, v in self.exact.items() if len(k) >= 12}
        self.long_re = re.compile("|".join(re.escape(k) for k in sorted(long_, key=len, reverse=True))) if long_ else None
        self.long = long_
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
        if self.long_re and self.long_re.search(plain):
            def sub(m):
                self.hits[m.group(0)] += 1
                return self.long[m.group(0)]
            return html.escape(self.long_re.sub(sub, plain), quote=False)
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


def apply_dir(root: Path, site: str, dry: bool = False) -> Counter:
    entries = load_rewrites(site)
    if not entries:
        return Counter()
    rw = Rewriter(entries)
    for f in nj.walk_files(root, (".html", ".htm")):
        rel = str(f.relative_to(root)).replace("\\", "/")
        if nj.EXEMPT_PATH.search(rel):
            continue
        raw = f.read_text(encoding="utf-8")
        new = rw.page(raw)
        if new != raw and not dry:
            f.write_text(new, encoding="utf-8", newline="")
    return rw.hits


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


def judge_prompt(site: str, batch: list[Unit]) -> str:
    ex = [e for e in examples()]
    ex_txt = "\n".join(f"- 「{e['before']}」→「{e['after']}」({e['site']}・{e['kind']}。{e.get('why', '')})" for e in ex)
    items = [{"id": i + 1, "kind": u.kind, "text": u.text} for i, u in enumerate(batch)]
    return f"""あなたは日本語の校閲者です。次の「短い言葉」(見出し・ボタン・ラベル・メニュー・タイトル・説明文・代替テキスト)が、日本語のサイトの文言として自然かを一つずつ判定してください。
サイト: {site}。{SITE_STYLE.get(site, '')}
基準: ふつうの人がその場面で自然に言うか。堅い複合語(掘り下げる・〜の位置)、翻訳調、お役所の言い回し、内輪の編集語、名詞をつないだだけの見出し、AIが作ったような決まり文句は不自然。短く、ふつうの言葉で。自然なら直さない(自然なものを無理に変えない)。
オーナーが実際に直した例(必ず見本にすること):
{ex_txt}
直すのは不自然な部分だけ。自然な語や言い回しは残し、できるだけ少ない変更にする(全体を書き換えない)。
守ること: 意味・事実・数字・日付・固有名(作品名・商品名・店名・イベント名・人名・地名)・「」の引用・英字・カタカナの名前は変えない。新しい主張や体験(試した・必ず・最安など)を足さない。直し案は元の言葉と同じ程度の長さにする。
出力: JSONだけ(前後に説明を書かない)。形式: {{"items":[{{"id":1,"natural":true,"better":"","why":"","confidence":""}}]}}。natural が false のときだけ better に直し案、why に一言の理由、confidence に "high"(誰が読んでも不自然・直し案のほうが明らかによい)か "low"(好みの差)。固有名・データ由来の名前、画面の読み上げ用の標準的な語(パンくず 等)は natural:true。
入力:
{json.dumps(items, ensure_ascii=False)}
"""


def verify_prompt(site: str, pairs: list[tuple[str, str]]) -> str:
    items = [{"id": i + 1, "before": a, "after": b} for i, (a, b) in enumerate(pairs)]
    return f"""あなたは日本語の校閲者です。サイト({site})の文言の直し案が、元の文言と同じ意味・同じ事実のままか、一つずつ確かめてください。
同じ意味でない例: 内容が変わる・足される・減る(数字、条件、対象、注意点、出典を含む)、別の物の言い方になる、トーンが大きく変わる、かえって不自然になる。語を言い換えただけで意味が同じなら true。
出力: JSONだけ。形式: {{"items":[{{"id":1,"same_meaning":true,"natural":true,"problem":""}}]}}。same_meaning は意味が同じか、natural は直し案が自然な日本語か。
入力:
{json.dumps(items, ensure_ascii=False)}
"""


def verify(site: str, pairs: list[tuple[str, str]], runner=None) -> dict[int, bool]:
    """A second look at the rewordings that passed the checks: same meaning AND natural.  Anything not answered is not accepted."""
    runner = runner or run_codex
    answer = parse_judgement(runner(verify_prompt(site, pairs)), len(pairs))
    return {i: bool(it.get("same_meaning")) and bool(it.get("natural", True)) for i, it in answer.items()}


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


def judge(units: dict[str, Unit], site: str, batches: int = 3, accept: bool = False, runner=run_codex, today: str | None = None, verifier=None) -> dict:
    today = today or dt.date.today().isoformat()
    judged = load_judged(site)
    stats = Counter()
    todo = pending_units(units, site, judged)
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
            if it.get("natural", True) or not (it.get("better") or "").strip():
                judged[key_of(u.text)] = {"text": u.text, "natural": True, "at": today}
                stats["natural"] += 1
                continue
            better = norm(it["better"])
            problems = check_rewrite(u.text, better, site, u.kind)
            rec = {"text": u.text, "natural": False, "better": better, "why": it.get("why", ""), "at": today, "kind": u.kind, "confidence": str(it.get("confidence", ""))}
            if problems:
                rec["status"] = "rejected"
                rec["problems"] = problems
                stats["rejected"] += 1
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
                    ok, _ = add_entry(site, u.text, rec["better"], by="codex", why=rec["why"], kind=u.kind, today=today)
                    rec["status"] = "accepted" if ok else "duplicate"
                    stats["accepted" if ok else "duplicate"] += 1
                else:
                    rec["status"] = "proposed"
                    rec["problems"] = ["not confirmed by the second look (meaning or naturalness)"]
                    stats["proposed"] += 1
        save_judged(site, judged)
    stats["pending_after"] = max(0, len(todo) - batches * BATCH)
    return dict(stats)


# --------------------------------------------------------------------------------------------------------------------------------- the source (sites/<name>/)
SRC_EXT = {".py", ".json", ".md", ".txt", ".tpl", ".html", ".js"}


def source_files(site: str) -> list[Path]:
    base = ROOT / "sites" / site
    return [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SRC_EXT and not any(x in p.parts for x in ("__pycache__", "dist", "release", "assets_retired", "node_modules"))]


def source_plan(site: str) -> list[tuple[Path, str, str, int]]:
    plan = []
    entries = [e for e in load_rewrites(site) if not e.get("in_source")]
    for p in source_files(site):
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for e in entries:
            old, new = e["from"], e["to"]
            if len(old) >= 12:
                n = raw.count(old)
            else:                                           # a short text: only as a whole string / element, never inside a longer sentence
                n = sum(raw.count(f"{q}{old}{r}") for q, r in (('"', '"'), ("'", "'"), (">", "<")))
            if n:
                plan.append((p, old, new, n))
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
        new_raw = raw
        for old, new, n in items:
            if len(old) >= 12:
                new_raw = new_raw.replace(old, new)
            else:
                for q, r in (('"', '"'), ("'", "'"), (">", "<")):
                    new_raw = new_raw.replace(f"{q}{old}{r}", f"{q}{new}{r}")
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
            s.add_argument("--sentences", action="store_true", help="also ask about the body sentences that naturaljp finds suspicious (mid and high)")
        if name in ("extract", "flags"):
            s.add_argument("--limit", type=int, default=40)
        if name == "apply":
            s.add_argument("--dry", action="store_true")
    a = sub.add_parser("add")
    a.add_argument("--site", required=True)
    a.add_argument("--from", dest="old", required=True)
    a.add_argument("--to", required=True)
    a.add_argument("--by", default="owner")
    a.add_argument("--why", default="")
    a.add_argument("--kind", default="heading")
    a.add_argument("--force", action="store_true", help="skip the checks (an owner's own correction)")
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
        hits = apply_dir(root, site or "", args.dry)
        print(f"{sum(hits.values())} rewording(s) applied in {len(hits)} text(s) for {site}" + (" (dry run)" if args.dry else ""))
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
        st = judge(units, site or "", args.batches, args.accept)
        print(json.dumps(st, ensure_ascii=False))
        return 1 if st.get("failed_batches") else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
