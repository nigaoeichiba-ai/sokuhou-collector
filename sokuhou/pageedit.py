"""pageedit: one page, one Codex call, rewritten as a human editor would (the owner's order of 2026-10-17: raise the writing itself, not one sentence at a time).

    python -m sokuhou.styleloop edit --site yorokobu --page guide/ochugen/index.html [--build DIR] [--dry]   # one page of the built site
    python -m sokuhou.styleloop edit --site yorokobu --next 3                                              # the next 3 pages never edited (or whose text changed)

The instruction to the editor is `sokuhou-sites/docs/STYLE_EDITOR_PROMPT_JA.md` (the part between the two marker lines; its models and word lists are read by Codex itself, read-only).
Codex gets the page as a list `id | kind | text` in display order and returns JSON: diagnosis, edits (id, after, why), deleted, needs_check, structure_suggestions.
Only the invariants are checked by machine (numbers, names, claims, markup, the site's own rules - `styleloop.check_rewrite`, without the 'small edit' limit); an edit that passes goes into the
rewrite dictionary (applied after the build, as every dictionary line).  What a dictionary cannot do - delete a paragraph, move a section - stays a proposal in the report.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from sokuhou import naturaljp as nj
from sokuhou import styleloop as sl

DOCS = sl.ROOT.parent / "sokuhou-sites" / "docs"
EDITOR_PROMPT = DOCS / "STYLE_EDITOR_PROMPT_JA.md"
MAX_UNITS = 90                      # one call: the title and every heading, plus up to this many body units

CAPTURE = {"p", "li", "td", "th", "dd", "dt", "h1", "h2", "h3", "h4", "h5", "h6", "button", "label", "summary", "figcaption", "caption", "legend"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "code", "pre", "textarea", "blockquote", "cite", "select", "nav", "footer", "header", "aside", "form"}
KIND = {"h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading", "h6": "heading", "button": "button",
        "label": "label", "summary": "label", "figcaption": "label", "caption": "label", "legend": "label", "th": "label", "p": "para", "li": "item", "td": "item", "dd": "item", "dt": "item"}
SITE_INFO = {          # from the editor prompt's "サイト別の入れ替え値"
    "yorokobu": dict(dict_file="gift_ja.json", reader="失敗せず短時間で決めたい大人", rules="落ち着いた「です・ます」、「ね」「よ」「ぜんぶ」は使わない(例文メッセージを除く)、読点は意味の切れ目だけ(commas.py)、体験を装わない、マスコットなし"),
    "kuma": dict(dict_file="kuma_ja.json", reader="数字と日付を知りたい人", rules="事実を短く、結論(数字・日付・場所)を先に、出典を添える、目撃・出没の語の使い分けを変えない"),
    "saichin": dict(dict_file="saichin_ja.json", reader="数字と日付を知りたい人", rules="事実を短く、結論(数字・日付・場所)を先に、出典を添える、答申・改定・発効の語の使い分けを変えない"),
    "minna": dict(dict_file="minna_ja.json", reader="Web・イラスト・出版のプロと個人", rules="ふつうの日本語、漢字にできる語は漢字に、読点は0〜2個、利用条件の意味を変えない"),
    "atomou": dict(dict_file="atomou_ja.json", reader="中学生以上", rules="ひらがなを増やさない、分かち書きしない、実在しない機能を書かない"),
}
PAGE_KINDS = {"guide": "贈り方ガイド", "gift": "相手別の贈り物のまとめ", "pick": "商品の紹介", "picks": "今日のおすすめ", "read": "読みもの", "shogatsu": "お正月の特集",
              "compare": "比較", "data": "データの記事", "ranking": "ランキング", "message": "メッセージ例", "occasion": "行事のまとめ", "theme": "テーマの一覧", "diagnosis": "診断の結果",
              "illust": "素材の紹介", "series": "素材シリーズの紹介", "genre": "素材の一覧", "e": "日付カード", "c": "日付カードの一覧", "kyou": "日付の一覧", "research": "研究ノート"}


class PageUnit:
    def __init__(self, uid, kind, text, editable):
        self.id, self.kind, self.text, self.editable = uid, kind, text, editable


class _Page(HTMLParser):
    """The displayed text of a page in order.  A unit is editable when it is ONE text node (the dictionary replaces whole text nodes); one with a link or emphasis inside is shown, read-only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units: list[tuple[str, str, bool]] = []
        self.stack: list[list] = []          # [tag, nodes, has_child_tags]
        self.skip = 0
        self.title: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            if (a.get("name") or "").lower() == "description" and a.get("content"):
                self.units.append(("note", sl.norm(a["content"]), True))
            return
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if tag == "title":
            self.in_title = True
            return
        if self.skip:
            return
        if self.stack and tag not in CAPTURE:
            self.stack[-1][2] = True         # a link, an emphasis or a break inside
        if tag in CAPTURE:
            self.stack.append([tag, [], False])

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if tag == "title":
            self.in_title = False
            t = sl.norm("".join(self.title))
            if t:
                self.units.insert(0, ("title", t, True))
            return
        if self.skip or tag not in CAPTURE:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                _, nodes, inline = self.stack[i]
                del self.stack[i:]
                nodes = [n for n in nodes if n.strip()]
                if nodes:
                    text = sl.norm(nodes[0]) if len(nodes) == 1 else sl.norm(" ".join(nodes))
                    editable = len(nodes) == 1                       # one text node: the dictionary can replace it exactly (a tag around it does not matter)
                    if re.search(rf"[{nj.JP}]", text):
                        self.units.append((KIND[tag], text, editable))
                break

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        elif not self.skip and self.stack:
            self.stack[-1][1].append(data)


def looks_like_third_party(text: str, kind: str = "para") -> bool:
    """A shop's product title, a price line, a rating: data of others, shown but not edited.  (The page's own title has spaces around its bar; that is not a product.)"""
    if kind in ("title", "note"):
        return False
    spaces = 4 if kind == "heading" else 3
    return sl.protected_name(text) or "★" in text or "¥" in text or text.count(" ") >= spaces or bool(re.match(r"^[\d,.\s円%％()（）/\-〜~]+$", text))


def page_units(raw: str) -> list[PageUnit]:
    p = _Page()
    p.feed(raw)
    out = []
    for i, (kind, text, editable) in enumerate(p.units, 1):
        out.append(PageUnit(f"u{i}", kind, text, editable and not looks_like_third_party(text, kind)))
    return out


def content_hash(units: list[PageUnit]) -> str:
    return hashlib.sha1("".join(u.kind + u.text for u in units).encode("utf-8")).hexdigest()[:12]


def chunks(units: list[PageUnit]) -> list[list[PageUnit]]:
    """One call for a short page.  A long page is cut at a heading; the title and every heading go with each part (to see the structure)."""
    if len(units) <= MAX_UNITS:
        return [units]
    spine = [u for u in units if u.kind in ("title", "heading")]
    parts, cur, count = [], [], 0
    for u in units:
        if u.kind == "heading" and count >= MAX_UNITS - len(spine):
            parts.append(cur)
            cur, count = [], 0
        cur.append(u)
        count += u.kind not in ("title", "heading")
    if cur:
        parts.append(cur)
    out = []
    for part in parts:
        ids = {u.id for u in part}
        out.append(sorted(part + [u for u in spine if u.id not in ids], key=lambda u: int(u.id[1:])))
    return out


def prompt_template() -> str:
    t = EDITOR_PROMPT.read_text(encoding="utf-8")
    m = re.search(r"^=== ここから ===\s*$(.*?)^=== ここまで ===\s*$", t, re.S | re.M)
    if not m:
        raise RuntimeError("the editor prompt has no 'ここから / ここまで' block")
    return m.group(1).strip()


def page_kind(rel: str) -> str:
    first = rel.strip("/").split("/")[0]
    return PAGE_KINDS.get(first, "案内文") if "/" in rel.strip("/") else "トップページ・案内文"


def build_prompt(site: str, rel: str, units: list[PageUnit]) -> str:
    info = SITE_INFO[site]
    lines = [f"{u.id} | {u.kind}{'' if u.editable else '(編集不可・参考)'} | {u.text}" for u in units]
    t = prompt_template()
    for k, v in {"{{SITE_DICT}}": info["dict_file"], "{{SITE}}": site, "{{READER}}": info["reader"], "{{PAGE_KIND}}": page_kind(rel), "{{SITE_RULES}}": info["rules"],
                 "{{EXTRA_FIXED}}": "商品名・店名・価格・星の評価は第三者のデータ。(編集不可・参考)と書いた単位は直さない(edits に入れない)", "{{UNITS}}": chr(10).join(lines)}.items():
        t = t.replace(k, v)
    return t


def parse_edit(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in the answer")
    d = json.loads(m.group(0))
    if not isinstance(d, dict) or not isinstance(d.get("edits", []), list):
        raise ValueError("the answer has no edits list")
    return d


def edited_path(site: str) -> Path:
    return sl.DATA / "edited" / f"{site}.json"


def load_edited(site: str) -> dict:
    try:
        return json.loads(edited_path(site).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_edited(site: str, d: dict) -> None:
    f = edited_path(site)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + chr(10), encoding="utf-8", newline="\n")


def tidy(site: str, after: str) -> str:
    """Deterministic fixes the editor cannot be trusted to make: yorokobu's own comma rule (sites/yorokobu/commas.py) is applied to the rewording."""
    after = sl.norm(after)
    if site == "yorokobu":
        try:
            from sites.yorokobu import commas
            after = commas.lighten_short(after) if len(after) <= commas.SHORT_PHRASE else commas.lighten(after)
        except ImportError:
            pass
    return after


# the careful ways of saying things that an editor must not turn into flat statements ("場合があります" -> "です")
HEDGE = re.compile(r"場合があります|場合もあります|とされ|と言われ|かもしれ|ことがあります|ことも|目安|一般的|傾向|ようです|可能性|前後|ほど|ことが多い|がち|多くの")
CLAIM_KINDS = ("para", "item", "note")


def hedges(text: str) -> int:
    return len(HEDGE.findall(text))


def claims_prompt(site: str, pairs: list[tuple[str, str]]) -> str:
    items = [{"id": i + 1, "before": a, "after": b} for i, (a, b) in enumerate(pairs)]
    return f"""あなたは日本語の校閲者です。サイト({site})の本文の書き直し(before→after)が、元の意味を保っているかを一組ずつ確かめてください。見るのは次の3つだけです。
- added_claim: 元に無い断定・理由・事実・一般化が足されていないか(元の文から読み取れない「〜だから」「〜に向く」「〜できる」などを含む)。
- hedge_removed: 「場合があります」「とされています」「かもしれません」「ことがあります」「目安」「一般的」「ほど」「前後」のような控えめな言い方が消えて、言い切りになっていないか。
- condition_dropped: 元の条件(いつ・誰に・どの場合・どこで・どれくらい)が落ちていないか。
いずれも、少しでも当てはまれば true にして、problem に一言で書く。文章の良し悪しは判定しない。
出力: JSONだけ(前後に説明を書かない)。形式: {{"items":[{{"id":1,"added_claim":false,"hedge_removed":false,"condition_dropped":false,"problem":""}}]}}
入力:
{json.dumps(items, ensure_ascii=False)}
"""


def check_claims(site: str, pairs: list[tuple[str, str]], runner) -> dict[int, str]:
    """{index (1-based): problem} for the rewritings that add a statement, lose a hedge or drop a condition.  A rewriting the checker did not answer about is a problem too."""
    answer = sl.parse_judgement(runner(claims_prompt(site, pairs)), len(pairs))
    out = {}
    for i in range(1, len(pairs) + 1):
        it = answer.get(i)
        if it is None:
            out[i] = "the claims check gave no answer"
        elif it.get("added_claim") or it.get("hedge_removed") or it.get("condition_dropped"):
            kinds = [k for k, f in (("added claim", "added_claim"), ("hedge removed", "hedge_removed"), ("condition dropped", "condition_dropped")) if it.get(f)]
            out[i] = f"{'/'.join(kinds)}: {str(it.get('problem', ''))[:80]}"
    return out


def check_edit(site: str, unit: PageUnit, after: str) -> list[str]:
    """The invariants for an editor's rewrite of one unit.  A page edit may change a paragraph a lot, so the 'small edit' limit of the sentence mode is not applied."""
    kind = {"title": "heading", "heading": "heading", "button": "heading", "label": "heading"}.get(unit.kind, "para")
    problems = sl.check_rewrite(unit.text, sl.norm(after), site, kind, small_edit=False)
    if unit.kind in CLAIM_KINDS and hedges(after) < hedges(unit.text):
        problems.append(f"careful wording removed (hedges {hedges(unit.text)} -> {hedges(after)})")
    return problems


def edit_page(site: str, rel: str, raw: str, runner=None, today: str | None = None, accept: bool = True, dry: bool = False, verifier=None) -> dict:
    """Edit one page (one Codex call per chunk).  Returns the report; the accepted edits are in the dictionary unless dry."""
    today = today or dt.date.today().isoformat()
    runner = runner or sl.run_codex
    units = page_units(raw)
    report = {"page": rel, "date": today, "hash": content_hash(units), "units": len(units), "diagnosis": [], "accepted": [], "rejected": [], "deleted": [], "needs_check": [],
              "structure_suggestions": [], "unchanged": 0, "failed": ""}
    by_id = {u.id: u for u in units}
    passed: list[tuple[PageUnit, str, str]] = []             # edits that passed the invariants; the claims check comes next
    for chunk in chunks(units):
        if dry:
            report["prompt"] = build_prompt(site, rel, chunk)
            return report
        try:
            d = parse_edit(runner(build_prompt(site, rel, chunk)))
        except Exception as e:                                   # a failure is a failure, never "nothing to fix"
            report["failed"] = str(e)[:200]
            return report
        report["diagnosis"] += [str(x) for x in d.get("diagnosis", [])][:6]
        report["structure_suggestions"] += [re.sub(r"u(\d+)", lambda m: f"「{by_id['u' + m.group(1)].text[:14]}…」" if "u" + m.group(1) in by_id else m.group(0), str(x)) for x in d.get("structure_suggestions", [])]
        report["unchanged"] += int(d.get("unchanged_count") or 0)
        for q in d.get("needs_check", []):
            if isinstance(q, dict) and q.get("id") in by_id:
                report["needs_check"].append({"text": by_id[q["id"]].text[:80], "question": str(q.get("question", ""))[:200]})
        for did in d.get("deleted", []):
            if did in by_id:
                report["deleted"].append(by_id[did].text[:100])
        for e in d.get("edits", []):
            u = by_id.get(e.get("id")) if isinstance(e, dict) else None
            after = tidy(site, str(e.get("after", ""))) if u else ""
            if u is None or not after:
                continue
            if not u.editable:
                report["rejected"].append({"text": u.text[:60], "problems": ["not editable (shown for reference only)"]})
                continue
            problems = check_edit(site, u, after)
            if problems:
                report["rejected"].append({"text": u.text[:60], "after": after[:80], "problems": problems})
                continue
            passed.append((u, after, str(e.get("why", ""))[:60]))
    # the second look at the paragraphs: no statement added, no careful wording lost, no condition dropped (a separate Codex call; if it fails, no paragraph is taken)
    long_ = [(u, a, w) for u, a, w in passed if u.kind in CLAIM_KINDS and len(u.text) >= 20]
    claim_problems: dict[int, str] = {}
    if long_:
        try:
            claim_problems = check_claims(site, [(u.text, a) for u, a, _ in long_], verifier or runner)
        except Exception as ex:
            claim_problems = {i: f"the claims check failed ({str(ex)[:60]}): not taken" for i in range(1, len(long_) + 1)}
            report["claims_check_failed"] = str(ex)[:120]
    bad = {id(long_[i - 1][0]): msg for i, msg in claim_problems.items()}
    for u, after, why in passed:
        if id(u) in bad:
            report["rejected"].append({"text": u.text[:60], "after": after[:80], "problems": [bad[id(u)]]})
            continue
        if accept and not dry:
            ok, why_ = sl.add_entry(site, u.text, after, by="editor", why=why, kind="note" if u.kind in CLAIM_KINDS else "heading", today=today, small_edit=False)
            if not ok and why_ != ["already in the dictionary"]:
                report["rejected"].append({"text": u.text[:60], "problems": why_})
                continue
        report["accepted"].append({"kind": u.kind, "from": u.text, "to": after, "why": why})
    return report


def next_pages(site: str, build: Path, n: int) -> list[tuple[str, str]]:
    """The next pages to edit: editorial pages (several editable paragraphs) never edited, or whose text changed since; oldest first."""
    done = load_edited(site)
    cand = []
    for f in nj.walk_files(build, (".html", ".htm")):
        rel = str(f.relative_to(build)).replace("\\", "/")
        if nj.EXEMPT_PATH.search(rel):
            continue
        raw = nj.published_text(f.read_text(encoding="utf-8"), site)
        units = page_units(raw)
        body = [u for u in units if u.editable and u.kind in ("para", "item") and len(u.text) >= 30]
        if len(body) < 3:
            continue
        h = content_hash(units)
        prev = done.get(rel)
        if prev and prev.get("hash") == h:
            continue
        cand.append((prev.get("date", "") if prev else "", -len(body), rel, raw))
    cand.sort()
    return [(rel, raw) for _, _, rel, raw in cand[:n]]
