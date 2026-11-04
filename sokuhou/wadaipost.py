"""wadai (topical-news posts): the post queue and the automatic checks, DRY RUN ONLY.

What this file is: code and rules.  What it is not: any content.  The queue (drafts, shortened affiliate links), the accounts file, the approvals and the
tokens live in the server's private folder (~/wadai-private/) and in GitHub Secrets (only their NAMES are used here); nothing of them is ever in this
repository (the repository is public; owner rule 2026-10-17).  Nothing here calls the Threads API: `Publisher` is an interface and the only
implementation is `DryRunPublisher`, which records what WOULD be posted.  The design is docs/new_sites/WADAI_DESIGN_2026-11-04.md (sections 3-4, 5, 12).

Checks (a finding has a code; the CLI prints codes and ids only, never the text of a draft, because the output may go to a public CI log):
 posts   P01 evidence   P02 alarm words   P03 faked experience   P04 authority/price words   P05 product data in the text (name, price, URL, brand)
         P06 length (emoji counted by UTF-8 bytes)   P07 link count   P08 PR line   P09 off-limits subjects   P10 layers (fact / view / preparation)
         P11 numbers must come from the facts   P12 repeats and similarity   P13 daily limit, gap, same type   P14 approval
 articles A01 layers in order   A02 layer mix   A03 each fact has a body and a date   A04 numbers   A05 proper nouns not in the ledger
         A06 criticism of a named party   A07 forbidden words   A08 price / product names   A09 update history really changed   A10 freshness
         A13 the party of a consumer trouble gets no product or path, and no individual victim (P16 is the same rule for posts)
         A18 no source talk in the public text   A19 each fact verified (primary, or two sources) in the private ledger
         A15 a lead, not opening with "not known" (P17 for posts)   A16 no "not known / not confirmed" in the body   A17 the four-line reader memo
Not implemented (needs a live feed or a page build): warning areas (P15), thin-page measure (A11), advertising label in the built page (A12), the natural-Japanese gate (A14).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

TEXT_LIMIT = 500
TEXT_MARGIN = 30                    # the real limit is 500; stay under 470 because emoji counting is by bytes
EVIDENCE_MAX_HOURS = 72             # a fact from an announcement is stale after 72 hours
SIM_CROSS, SIM_SAME, SIM_HOOK = 0.30, 0.45, 0.50     # as tools/cross_account_check.py
GAP_MIN = 90                        # minutes between posts of different accounts
GLOBAL_DAILY_MAX = 3                # breaking-news posts per day, all accounts together
SAME_KIND_DAYS = 7                  # the same product kind on the same account: once in 7 days
SAME_TOPIC_DAYS = 7                 # the same topic on two accounts: never within 7 days
SAME_TYPE_WINDOW = 3                # the same post type twice within the last 3 posts of an account is refused
POST_TYPES = {"T1S", "T2", "T3", "T4", "T5", "T6", "T7"}
FACT_KINDS = {"E": "calendar", "G": "government", "W": "weather", "M": "media"}      # topic kinds (design 2-1)

# ---- word lists (design 12-4) --------------------------------------------------------------------------------------------------------------
ALARM = ["緊急", "今すぐ", "命を守る", "危険です", "危険な", "手遅れ", "絶対", "必ず", "確実", "しないと大変", "買い占め", "売り切れ前", "急いで", "大変なことに"]
EXPERIENCE = ["使ってみた", "買ってみた", "愛用", "リピ", "うちの", "我が家", "実際に試", "私の家", "取材", "使っています", "買いました", "使いました", "試しました", "使ってます"]
AUTHORITY = ["専門家によると", "専門家は", "医師", "関係者によると", "調査によると", "満足度", "人気No", "売れ筋", "話題の", "バズ", "口コミ", "レビュー"]
PRICE_RE = re.compile(r"\d[\d,]*\s*円|最安|格安|お得|安い|ランキング|No\.?\s?1|第\s?1位|[1１]位|ポイント\d|送料無料")
CRITICISM = ["隠蔽", "怠慢", "責任", "が悪い", "のせい", "失態", "ずさん", "無責任", "許せない", "ひどい", "だらしない"]
ORG_RE = re.compile(r"[一-龥ァ-ヴーA-Za-z]{2,}(?:社|庁|省|氏|会社|銀行|電力|協会|機構|センター|委員会|知事|首相|大臣|事業者)")
VICTIM_INDIVIDUAL = ["被害女性", "被害男性", "被害者の女性", "被害者の男性", "遺族", "被害少女", "被害児童"]       # stories about an individual victim are not used (owner 2026-11-04)
LEGAL_ADVICE = ["違法です", "訴えられる", "必ず儲かる", "儲かる"]
# subjects that are off limits for this project (design 2-4); substring match
OFF_LIMITS = {
    "medical": ["効く", "治る", "治す", "改善する", "予防できる", "健康に", "免疫", "ダイエット", "サプリ", "医薬", "病気", "治療", "処方", "症状が"],
    "finance": ["投資", "FX", "暗号資産", "仮想通貨", "儲か", "利回り", "証券", "株価", "株式"],
    "alcohol": ["ボジョレー", "ワイン", "日本酒", "ビール", "飲酒"],
    "adult": ["アダルト", "成人向け", "18禁"],
    "gambling": ["カジノ", "パチンコ", "競馬", "ギャンブル"],
    "politics": ["選挙", "与党", "野党", "政権", "投票"],
}
ISSUERS = ["国民生活センター", "消費者庁", "気象庁", "防災庁", "内閣府", "消防庁", "国立天文台", "総務省", "経済産業省", "資源エネルギー庁", "厚生労働省", "国土交通省", "文部科学省", "IPA", "JPCERT", "首相官邸", "政府"]
HEDGE_END = re.compile(r"(そう|かも|かな|かもしれない|と考えられる|可能性がある|可能性も|ではないか|のではないか|だろう|と思う|かもね|ようだ|見方もある|見方ができる|そうです|かもしれません|かもです|可能性があります|可能性もあります|でしょう|ようです|ではないでしょうか|と思います|そうですね|手です|手があります|選択肢です|選択肢もあります|方法もあります|のもありです)$")
HEDGE_ANY = re.compile(r"(かもしれ|と考えられ|可能性が|可能性も|のではないか|だろう|と思う|そうで|そう[。!！\s]|かも[。!！\s]|かな[。!！\s]|でしょう|ようです|と思います)")
DATE_RE = re.compile(r"\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
URL_RE = re.compile(r"https?://\S+|\b[a-z0-9-]+\.(?:com|jp|net|org|to)/\S*", re.I)
# "we do not know" is never the main voice of a page or a post (owner 2026-11-04): what is not confirmed is left out, or goes to the update history (the end) as a short note
UNKNOWN_RE = re.compile(r"分からな|わからな|分かって(?:い)?な|確認できて(?:い)?な|確認できな|資料にな|読めて(?:い)?な|未確認|不明|裏付けは")
# the public text shows no sources (owner 2026-11-04): no media names, no "according to the press", no bracketed source notes.  The agency / office that announced a fact and the date stay: that is part of the fact.
MEDIA_NAMES = ["ITmedia", "Yahoo!ニュース", "時事通信", "共同通信", "日本経済新聞", "日経", "テレビ朝日", "テレ朝", "朝日新聞", "読売新聞", "毎日新聞", "産経", "東京新聞", "NHK", "livedoor", "ライブドア", "ビジネス+IT", "FNN", "tenki.jp", "埼玉新聞"]
SOURCE_TALK = re.compile(r"報道|報じ|伝えて|[（(][^）)]*(?:公式ページ|ニュース|新聞|通信|NEWS)[^）)]*[）)]|公式ページ(?:に|は)")
MEMO_KEYS = ("reader", "trouble", "feel", "action")        # who reads / what troubles them before reading / what the first sentence should make them feel / what they should do after reading
FORMULA_MARK = ("＝", "=", "×", "例だよ", "例です", "たとえば")
KATAKANA_RE = re.compile(r"[ァ-ヴー]{4,}")
QUOTED_RE = re.compile(r"[「『]([^」』]{2,20})[」』]")
NUMBERED_RE = re.compile(r"(?:第\s?\d+号|台風\d+号)")


@dataclass
class Finding:
    code: str
    item: str                       # the id of the post or the article
    msg: str                        # a short reason (may name the rule, never the draft's text unless verbose)
    detail: str = ""                # the offending snippet, shown only with --verbose

    def line(self, verbose=False) -> str:
        return f"{self.code} {self.item}: {self.msg}" + (f"  [{self.detail}]" if verbose and self.detail else "")


# ---- helpers ------------------------------------------------------------------------------------------------------------------------------
def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0xFE0F, 0x200D, 0x2B50, 0x2B55, 0x2194, 0x2195, 0x21A9) or unicodedata.category(ch) == "So"


def weighted_length(text: str) -> int:
    """Threads counts an emoji by its UTF-8 bytes (official: 'Emojis count as their UTF-8 byte count'); every other character counts 1."""
    return sum(len(ch.encode("utf-8")) if _is_emoji(ch) else 1 for ch in text)


def grams(s: str, n: int = 3) -> set:
    s = re.sub(r"\s+", "", s)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def jaccard(a: str, b: str) -> float:
    A, B = grams(a), grams(b)
    return len(A & B) / len(A | B) if A | B else 0.0


def first_line(s: str) -> str:
    return s.strip().split("\n")[0]


def _strip_tail(s: str) -> str:
    """The sentence without trailing emoji, spaces and sentence marks (so that the ending word can be read)."""
    s = s.rstrip()
    while s and (_is_emoji(s[-1]) or s[-1] in "。！？!?　 ☺️…~〜"):
        s = s[:-1]
    return s


def _nums(text: str) -> set:
    return {n.replace(",", "") for n in NUM_RE.findall(text)}


def _when(p: dict) -> datetime:
    return datetime.fromisoformat(p["scheduled_at"])


def _without(text: str, phrases) -> str:
    """Official names that contain a banned word (e.g. 緊急要請, the name of the request) may be named once the editor lists them in ctx["allowed_phrases"]."""
    for ph in phrases:
        text = text.replace(ph, "")
    return text


def _hits(text: str, words) -> list:
    return [w for w in words if w in text]


# ---- post checks ---------------------------------------------------------------------------------------------------------------------------
def check_post(p: dict, ctx: dict | None = None) -> list[Finding]:
    """One post against the single-post rules.  ctx: {"product_terms": [...], "allowed_terms": [...], "now": datetime}."""
    ctx = ctx or {}
    out: list[Finding] = []
    pid = str(p.get("id", "?"))
    body, reply = p.get("body", ""), p.get("reply", "")
    both = _without(body + "\n" + reply, ctx.get("allowed_phrases", []))

    def add(code, msg, detail=""):
        out.append(Finding(code, pid, msg, detail))

    # P01 evidence (a fact needs its source id and date; announcements go stale)
    kind = p.get("topic_kind")
    if kind not in FACT_KINDS:
        add("P01", "topic_kind must be one of E/G/W/M")
    ev_id, ev_date = p.get("evidence_id"), p.get("evidence_date")
    if p.get("type") in ("T1S", "T2") and not ev_id:
        add("P01", "evidence_id is required for T1S and T2")
    if kind in ("G", "W", "M"):
        if not ev_date:
            add("P01", "evidence_date is required for G/W/M topics")
        else:
            try:
                age = _when(p) - datetime.fromisoformat(ev_date)
                if age > timedelta(hours=EVIDENCE_MAX_HOURS):
                    add("P01", f"the evidence is older than {EVIDENCE_MAX_HOURS} hours")
                if age < timedelta(0):
                    add("P01", "the evidence is dated after the post")
            except ValueError:
                add("P01", "evidence_date / scheduled_at not ISO")
        if not p.get("human_checked"):
            add("P01", "G/W/M facts need human_checked (a person read the official text)")
    if kind == "E" and p.get("calendar_status") not in ("◎", "○"):
        add("P01", "a calendar topic needs calendar_status ◎ or ○ (confirmed)")

    # P02-P04, P09 word lists (body and reply)
    for w in _hits(both, ALARM):
        add("P02", "alarm word", w)
    for w in _hits(both, EXPERIENCE):
        add("P03", "faked experience", w)
    for w in _hits(both, AUTHORITY) + [m.group(0) for m in PRICE_RE.finditer(both)]:
        add("P04", "authority / price / rank word", w)
    for w in _hits(both, LEGAL_ADVICE):
        add("P09", "legal / money advice", w)
    for w in _hits(both, VICTIM_INDIVIDUAL):
        add("P09", "an individual victim", w)
    for name in p.get("parties", []):                     # the company that caused the trouble is never named in a post and never gets a path
        if name and name in both:
            add("P16", "the party of the trouble is named in the text", name)
    for cat, words in OFF_LIMITS.items():
        for w in _hits(both, words):
            add("P09", f"off-limits subject ({cat})", w)

    # P05 product data must not enter a Threads text (Rakuten rule 10-1 (9)): no URL, no price, no product / brand terms in the body
    if URL_RE.search(body):
        add("P05", "a URL in the body (links go in the reply)", URL_RE.search(body).group(0))
    for t in ctx.get("product_terms", []):
        if t and t in both:
            add("P05", "a product / brand term in the text", t)

    # P06 length
    for label, text in (("body", body), ("reply", reply)):
        n = weighted_length(text)
        if n > TEXT_LIMIT - TEXT_MARGIN:
            add("P06", f"{label} is {n} weighted characters (limit {TEXT_LIMIT - TEXT_MARGIN})")
    if not body.strip():
        add("P06", "empty body")

    # P07 links: none in the body, at most one in the reply
    if len(URL_RE.findall(reply)) > 1:
        add("P07", "more than one URL in the reply")

    # P08 PR line (a reply with a link starts with 【PR】, the second line says what the page offers; the body has no 【PR】)
    if reply and p.get("ads", True):          # a reply that carries no advertising (ads: false) needs no 【PR】
        lines = [l for l in reply.strip().split("\n") if l.strip()]
        if not lines or not lines[0].startswith("【PR】"):
            add("P08", "the reply must start with 【PR】")
        else:
            rest = lines[0][len("【PR】"):].strip()
            desc = rest or (lines[1].strip() if len(lines) > 1 else "")      # the text may follow 【PR】 on its line or be the next line
            if not desc or URL_RE.search(desc):
                add("P08", "【PR】 must be followed by a line saying what the link offers (not a URL)")
    if "【PR】" in body:
        add("P08", "【PR】 belongs to the reply, not the body")

    # P10 layers of T1S: fact / view / preparation (design 12-3)
    if p.get("type") == "T1S":
        lines = [l for l in body.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            add("P10", "T1S needs at least 3 lines (fact, view, preparation)")
        else:
            fact, middle = lines[0], lines[1:-1]
            if HEDGE_ANY.search(fact):
                add("P10", "the fact line holds a hedge (views belong to the middle lines)")
            if not (DATE_RE.search(fact) or any(i in fact for i in ISSUERS + [str(p.get("issuer", "-"))])):
                add("P10", "the fact line names neither a date nor an issuer")
            if not any(HEDGE_END.search(_strip_tail(l)) for l in middle):
                add("P10", "no middle line reads as a view (ends with そう / かも / 可能性…)")

    # P17 the first two lines must not open with "not known / not confirmed"
    opening = "\n".join([l for l in body.strip().split("\n") if l.strip()][:2])
    if UNKNOWN_RE.search(opening):
        add("P17", "the opening lines say something is not known / not confirmed", UNKNOWN_RE.search(opening).group(0))

    # P18 no source talk in the public text (media names, "according to reports", bracketed source notes)
    for m in [m for m in MEDIA_NAMES if m in both] + [x.group(0) for x in SOURCE_TALK.finditer(both)]:
        add("P18", "the text shows a source (media name / report wording); keep the announcer and the date, drop the source", m)

    # P11 numbers: each number in the body is in the facts, in the evidence date, or in a formula line marked as an example
    allowed = set()
    for f in p.get("facts", []):
        allowed |= _nums(f)
    for d in (ev_date or "", p.get("scheduled_at", "")[:10], p.get("calendar_date", "")):
        allowed |= {str(int(x)) for x in re.findall(r"\d+", d)}
    for line in body.split("\n"):
        if any(m in line for m in FORMULA_MARK):
            allowed |= _nums(line)
    for n in sorted(_nums(body) - allowed):
        add("P11", "a number that is in none of the facts / the date / a formula line", n)
    return out


def check_batch(posts: list[dict], accounts: dict | None = None, history: list[dict] | None = None, ctx: dict | None = None) -> list[Finding]:
    """The rules that look at several posts: repeats (P12), daily limits and gaps (P13), approval (P14).  `history` are the posts already out."""
    ctx = ctx or {}
    accounts = accounts or {}
    out: list[Finding] = []
    allp = list(history or []) + list(posts)
    acc_cfg = {a["id"]: a for a in accounts.get("accounts", [])} if accounts else {}
    for p in posts:
        pid = str(p.get("id", "?"))
        for q in allp:
            if q is p or q.get("id") == p.get("id"):
                continue
            same = q.get("account") == p.get("account")
            if abs((_when(q) - _when(p)).days) > 30:
                continue
            sim = jaccard(p.get("body", ""), q.get("body", ""))
            if sim > (SIM_SAME if same else SIM_CROSS):
                out.append(Finding("P12", pid, f"body too similar to {q.get('id')} ({sim:.2f})"))
            if first_line(p.get("body", "")) and jaccard(first_line(p["body"]), first_line(q.get("body", ""))) > SIM_HOOK:
                out.append(Finding("P12", pid, f"first line too similar to {q.get('id')}"))
            if not same and p.get("topic_id") and p.get("topic_id") == q.get("topic_id") and abs((_when(q) - _when(p)).days) < SAME_TOPIC_DAYS:
                out.append(Finding("P12", pid, f"the same topic is on another account ({q.get('id')}) within {SAME_TOPIC_DAYS} days"))
            if same and p.get("product_kind") and p.get("product_kind") == q.get("product_kind") and 0 < abs((_when(q) - _when(p)).days) < SAME_KIND_DAYS:
                out.append(Finding("P12", pid, f"the same product kind on this account within {SAME_KIND_DAYS} days ({q.get('id')})"))
            if not same and p.get("product_kind") and p.get("product_kind") == q.get("product_kind") and abs((_when(q) - _when(p)).days) < 30:
                out.append(Finding("P12", pid, f"the same product kind on another account within 30 days ({q.get('id')})"))
            if not same and abs((_when(q) - _when(p)).total_seconds()) < GAP_MIN * 60:
                out.append(Finding("P13", pid, f"less than {GAP_MIN} minutes from another account's post ({q.get('id')})"))
        # same type twice within the last 3 posts of the account
        mine = sorted([q for q in allp if q.get("account") == p.get("account") and _when(q) <= _when(p)], key=_when)
        recent = [q for q in mine if q.get("id") != p.get("id")][-(SAME_TYPE_WINDOW - 1):]
        if p.get("type") and sum(1 for q in recent if q.get("type") == p.get("type")) >= 2:
            out.append(Finding("P13", pid, f"the same type {p.get('type')} three times in a row on this account"))
        # daily limits
        day = p["scheduled_at"][:10]
        same_day = [q for q in allp if q["scheduled_at"][:10] == day and q.get("breaking", True)]
        if len(same_day) > GLOBAL_DAILY_MAX:
            out.append(Finding("P13", pid, f"more than {GLOBAL_DAILY_MAX} breaking posts on {day}"))
        cfg = acc_cfg.get(p.get("account"))
        if cfg:
            n = sum(1 for q in same_day if q.get("account") == p.get("account"))
            if n > cfg.get("daily_max", 1):
                out.append(Finding("P13", pid, f"over the account's daily_max ({cfg.get('daily_max', 1)})"))
            if not cfg.get("enabled"):
                out.append(Finding("P14", pid, "the account is not enabled"))
            elif p.get("topic_category") and cfg.get("categories") and p["topic_category"] not in cfg["categories"]:
                out.append(Finding("P14", pid, "the topic category is not assigned to this account"))
        elif accounts:
            out.append(Finding("P14", pid, "the account is not in accounts.json"))
    # approval of the type, product kind and wording range
    appr = ctx.get("approvals")
    if appr is not None:
        ok = {(a["type"], a.get("account", "*")): set(a.get("product_kinds", [])) for a in appr.get("approved", [])}
        for p in posts:
            kinds = ok.get((p.get("type"), p.get("account"))) or ok.get((p.get("type"), "*"))
            if kinds is None:
                out.append(Finding("P14", str(p.get("id")), "the type is not approved by the owner"))
            elif p.get("product_kind") not in kinds:
                out.append(Finding("P14", str(p.get("id")), "the product kind is outside the approved range"))
    return out


def check_posts_all(posts, accounts=None, history=None, ctx=None) -> list[Finding]:
    out = []
    for p in posts:
        out += check_post(p, ctx)
    return out + check_batch(posts, accounts, history, ctx)


# ---- article checks -----------------------------------------------------------------------------------------------------------------------
LAYER_ORDER = ["fact", "opinion", "prep", "history"]
LAYER_TITLES = {"fact": "確認できた事実", "opinion": "考察", "prep": "備え・選び方", "history": "更新履歴"}


def _sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]


def check_article(a: dict, ctx: dict | None = None) -> list[Finding]:
    """An article is {"id", "updated", "sections": [{"layer": fact|opinion|prep|history|other, "heading", "paras": [str], "bullets": [str]}], "ledger": [names],
    "public_values": [str], "previous": same-shape or None}.  Section text is every para and bullet."""
    ctx = ctx or {}
    aid = str(a.get("id", "?"))
    out: list[Finding] = []
    secs = a.get("sections", [])

    def text_of(s):
        # paragraphs and bullets, plus (reading edition) the boxes, the one-line summary and the figure captions: every public sentence is checked
        return (list(s.get("paras", [])) + list(s.get("bullets", [])) + [b.get("title", "") + " " + b.get("text", "") for b in s.get("boxes", [])]
                + ([s["summary"]] if s.get("summary") else []) + [f["caption"] for f in s.get("figures", []) if f.get("caption")])

    def add(code, msg, detail=""):
        out.append(Finding(code, aid, msg, detail))

    # A17 the reader memo (four lines written BEFORE the text) and A15 the lead (an answer or a fact the reader can take as their own)
    memo = a.get("reader_memo") or {}
    if any(not str(memo.get(k, "")).strip() for k in MEMO_KEYS):
        add("A17", "reader_memo needs reader / trouble / feel / action")
    lead = a.get("lead", "")
    if not lead.strip():
        add("A15", "the article has no lead")
    else:
        opening = _sentences(lead)
        if len(opening) > 2:
            add("A15", "the lead is longer than two sentences")
        first_text = next((t for s0 in secs for t in text_of(s0)), "")
        head2 = "".join((opening + _sentences(first_text))[:2])
        if UNKNOWN_RE.search(head2):
            add("A15", "the opening two sentences say something is not known / not confirmed", UNKNOWN_RE.search(head2).group(0))
    layers = [s.get("layer") for s in secs if s.get("layer") in LAYER_ORDER]
    # A01 the four layers, once each, in order; the heading names them
    if layers != LAYER_ORDER:
        add("A01", "the layers must be fact, opinion, prep, history, in this order, once each")
    for s in secs:
        lay = s.get("layer")
        if lay in LAYER_ORDER and LAYER_TITLES[lay] not in s.get("heading", ""):
            add("A01", f"the heading of the {lay} section must contain '{LAYER_TITLES[lay]}'")
    extra = list(a.get("tldr", [])) + ([a["poll"]["question"]] + list(a["poll"].get("options", [])) if a.get("poll") else [])
    alltext = _without("\n".join([t for s in secs for t in text_of(s)] + extra), ctx.get("allowed_phrases", []))
    fact_texts = [t for s in secs if s.get("layer") == "fact" for t in text_of(s)]
    # A02 layer mix
    for s in secs:
        for t in text_of(s):
            for sent in _sentences(t):
                hedged = bool(HEDGE_END.search(_strip_tail(sent)) or HEDGE_ANY.search(sent))
                if s.get("layer") == "fact" and hedged:
                    add("A02", "a hedged sentence in the fact section", sent[:20])
                if s.get("layer") == "opinion" and re.search(r"(である|となる|だった|になる|です|ます)[。！]?$", _strip_tail(sent) + "。") and not hedged and not any(m in sent for m in FORMULA_MARK):
                    # a flat statement in the opinion section: allowed only when it labels the view ("あくまで筆者の見方で…")
                    if "見方" not in sent and "編集部" not in sent and "場合" not in sent:
                        add("A02", "a flat statement in the opinion section (use a hedge, or label it)", sent[:20])
    # A16 "not known / not confirmed" is not said in the body at all (only the update history may carry a short note)
    for s in secs:
        if s.get("layer") == "history":
            continue
        for t in text_of(s):
            m = UNKNOWN_RE.search(t)
            if m:
                add("A16", "the body says something is not known / not confirmed (leave it out, or move a short note to the update history)", m.group(0))
    # A18 no source talk in any public text of the page (the record of what was checked lives in the private ledger: "verification")
    public = _without("\n".join([lead] + [t for s in secs for t in text_of(s)]), ctx.get("allowed_phrases", []))
    for m in [m for m in MEDIA_NAMES if m in public] + [x.group(0) for x in SOURCE_TALK.finditer(public)]:
        add("A18", "the page shows a source (media name / report wording / bracketed source note)", m)
    # A19 every fact bullet has a private verification record: a primary source, or at least two independent sources (a single source or a conflicting story is not published)
    ver = a.get("verification", [])
    fact_bullets = [t for s in secs if s.get("layer") == "fact" for t in s.get("bullets", [])]
    for i, _t in enumerate(fact_bullets):
        rec = next((v for v in ver if v.get("fact") == i), None)
        if not rec:
            add("A19", f"fact {i} has no verification record in the private ledger")
        elif not (rec.get("primary") or len(set(rec.get("sources", []))) >= 2):
            add("A19", f"fact {i} rests on a single source")
        elif rec.get("conflict"):
            add("A19", f"fact {i} has conflicting sources")
    # A03 every fact bullet names an issuer and a date
    for s in secs:
        if s.get("layer") != "fact":
            continue
        for t in s.get("bullets", []):
            if "発表されていない" in t or "分かっていない" in t:
                continue
            if not any(i in t for i in ISSUERS + list(ctx.get("issuers", []))):
                add("A03", "a fact bullet without an issuer", t[:15])
            if not DATE_RE.search(t):
                add("A03", "a fact bullet without a date", t[:15])
    # A04 numbers
    allowed = set()
    for t in fact_texts:
        allowed |= _nums(t)
    for v in a.get("public_values", []):
        allowed |= _nums(v)
    allowed |= _nums(str(a.get("updated", "")))
    for s in secs:
        for t in text_of(s):
            if s.get("layer") == "fact":
                continue
            for line in re.split(r"\n", t):
                if any(m in line for m in FORMULA_MARK):
                    allowed |= _nums(line)
    for n in sorted(_nums(DATE_RE.sub("", lead)) - allowed):
        add("A04", "a number in the lead that is in no fact", n)
    for s in secs:
        if s.get("layer") in ("fact", "history"):
            continue
        for t in text_of(s):
            t_clean = DATE_RE.sub("", t)
            for n in sorted(_nums(t_clean) - allowed):
                add("A04", "a number that is in no fact, no public value and no formula", n)
    # A05 proper nouns must be in the ledger (names the editors checked) or in the allowed terms
    ledger = [x for x in a.get("ledger", [])] + list(ctx.get("allowed_terms", [])) + ISSUERS
    found = set(ORG_RE.findall(alltext)) | set(QUOTED_RE.findall(alltext)) | set(NUMBERED_RE.findall(alltext)) | set(KATAKANA_RE.findall(alltext))
    for n in sorted(found):
        if not any(n in l or l in n for l in ledger):
            add("A05", "a proper noun not in the ledger", n)
    # A06 criticism near a named party
    for m in re.finditer("|".join(map(re.escape, CRITICISM)), alltext):
        window = alltext[max(0, m.start() - 30): m.end() + 30]
        if ORG_RE.search(window) or any(n in window for n in a.get("ledger", [])):
            add("A06", "criticism next to a named party", m.group(0))
    # A13 the party of the trouble: not in the preparation layer (no product or service of it is placed), and no individual victim anywhere
    for name in a.get("parties", []):
        for s in secs:
            if s.get("layer") == "prep" and any(name in tx for tx in text_of(s)):
                add("A13", "the party of the trouble is named in the preparation layer", name)
    for w in _hits(alltext, VICTIM_INDIVIDUAL):
        add("A13", "an individual victim", w)
    # A07 forbidden words, A08 price and product names
    for w in _hits(alltext, ALARM):
        add("A07", "alarm word", w)
    for w in _hits(alltext, EXPERIENCE):
        add("A07", "faked experience", w)
    for w in _hits(alltext, AUTHORITY) + _hits(alltext, LEGAL_ADVICE):
        add("A07", "authority / advice word", w)
    for cat, words in OFF_LIMITS.items():
        for w in _hits(alltext, words):
            add("A07", f"off-limits subject ({cat})", w)
    for m in PRICE_RE.finditer(alltext):
        add("A08", "a price / rank word", m.group(0))
    for t in ctx.get("product_terms", []):
        if t and t in alltext:
            add("A08", "a product / brand term", t)
    # A09 the update history must record a real change
    prev = a.get("previous")
    hist = [t for s in secs if s.get("layer") == "history" for t in text_of(s)]
    if prev is not None:
        prev_text = "\n".join(t for s in prev.get("sections", []) if s.get("layer") != "history" for t in text_of(s))
        now_text = "\n".join(t for s in secs if s.get("layer") != "history" for t in text_of(s))
        prev_hist = [t for s in prev.get("sections", []) if s.get("layer") == "history" for t in text_of(s)]
        if a.get("updated") != prev.get("updated") and prev_text == now_text:
            add("A09", "the update date changed but the text did not")
        if len(hist) > len(prev_hist) and prev_text == now_text:
            add("A09", "a history line was added but nothing else changed")
    if a.get("format") == "reading":
        out += check_reading(a)
    # A10 freshness (a warning-level finding: code A10 with 'warn'/'stale')
    try:
        age = (datetime.fromisoformat(ctx.get("today", datetime.now().date().isoformat())) - datetime.fromisoformat(str(a.get("updated")))).days
        if age >= 30:
            add("A10", "stale: not updated for 30 days or more (candidate for noindex)")
        elif age >= 7:
            add("A10", "warn: not updated for 7 days or more")
    except (ValueError, TypeError):
        add("A10", "the updated date is missing or not ISO")
    return out


# ---- the reading edition (format: "reading"): casual, with figures, boxes, a series and ways to take part (owner 2026-11-04) ---------------------------------
HARD_RE = re.compile(r"と考えられ|が望ましい|と言える|と言えま|であろう|と思われ|べきである|を要する|に留意|に資する|において|における|することが可能|を行う|を行いま|と推察|ものとする|の観点から|に際し|いただきたい|であると|である。")
POLITE_END = re.compile(r"(です|ます|ません|ください|ましょう|でした|ました|でしょう|ですね|ますね|ですよ|ますよ)[。！？!?]?$")
LUMP_CHARS = 130            # one paragraph longer than this is a lump of text
LUMP_RUN = 4                # this many plain paragraphs in a row, with no figure or box between them, is a wall of text


def reading_texts(a: dict) -> dict:
    """The public texts of a reading article by role."""
    secs = [s for s in a.get("sections", []) if s.get("layer") != "history"]
    paras = [t for s in secs for t in s.get("paras", [])]
    return {"lead": [a.get("lead", "")], "tldr": list(a.get("tldr", [])), "paras": paras, "bullets": [t for s in secs for t in s.get("bullets", [])],
            "summaries": [s.get("summary", "") for s in secs], "boxes": [b.get("text", "") for s in secs for b in s.get("boxes", [])],
            "captions": [f.get("caption", "") for s in secs for f in s.get("figures", [])]}


def check_reading(a: dict) -> list[Finding]:
    aid = str(a.get("id", "?"))
    out: list[Finding] = []

    def add(code, msg, detail=""):
        out.append(Finding(code, aid, msg, detail))

    T = reading_texts(a)
    allt = [t for v in T.values() for t in v]
    # A20 a hard, report-like style
    for t in allt:
        m = HARD_RE.search(t)
        if m:
            add("A20", "a stiff phrase (write it the way you would say it)", m.group(0))
    sents = [x for t in T["lead"] + T["paras"] for x in _sentences(t)]
    if sents:
        polite = sum(1 for x in sents if POLITE_END.search(x))
        if polite / len(sents) < 0.5:
            add("A20", f"only {polite} of {len(sents)} sentences end in です/ます (a です・ます tone is the base)")
    # A21 figures: at least one chart or table with data, and an illustration
    figs = [f for s in a.get("sections", []) for f in s.get("figures", [])] + ([a["hero"]] if a.get("hero") else [])
    if not any(f["kind"] in ("chart", "table") for f in figs):
        add("A21", "no chart or table (one or two figures made from public numbers)")
    if not any(f["kind"] == "image" for f in figs):
        add("A21", "no illustration")
    for f in figs:
        if f["kind"] == "image" and not f.get("alt"):
            add("A21", "an illustration without alt text")
        if f["kind"] == "chart" and not (f.get("title") and f.get("desc")):
            add("A21", "a chart without title and description")
    # A22 lumps of text
    for t in T["paras"]:
        if len(t) > LUMP_CHARS:
            add("A22", f"a paragraph of {len(t)} characters (cut it)", t[:12])
    for s in a.get("sections", []):
        if s.get("layer") == "history":
            continue
        if len(s.get("paras", [])) >= LUMP_RUN and not s.get("boxes") and not s.get("figures"):
            add("A22", f"section '{s.get('heading', '')[:10]}' has {len(s['paras'])} plain paragraphs and no figure or box")
    # A23 summaries: 3 lines at the top, one short line under each heading
    if len(a.get("tldr", [])) != 3:
        add("A23", "the 3-line summary needs exactly three lines")
    for t in a.get("tldr", []):
        if len(t) > 60:
            add("A23", "a summary line over 60 characters", t[:10])
    for s in a.get("sections", []):
        if s.get("layer") == "history":
            continue
        if not s.get("summary"):
            add("A23", f"section '{s.get('heading', '')[:10]}' has no one-line summary")
        elif len(s["summary"]) > 60:
            add("A23", "a section summary over 60 characters", s["summary"][:10])
    # A24 parts: tip and hack boxes, series, poll, next
    kinds = [b.get("kind") for s in a.get("sections", []) for b in s.get("boxes", [])]
    if "tip" not in kinds:
        add("A24", "no 豆知識 box")
    if "hack" not in kinds:
        add("A24", "no ライフハック box")
    se = a.get("series") or {}
    if not (se.get("name") and se.get("parent") and len(se.get("children", [])) >= 2):
        add("A24", "series needs a name, a parent and at least two child pages")
    if len(a.get("next", [])) < 1:
        add("A24", "no 'next to read'")
    po = a.get("poll") or {}
    if not (po.get("question") and 3 <= len(po.get("options", [])) <= 5):
        add("A24", "the poll needs one question and three to five choices")
    for t in [po.get("question", "")] + po.get("options", []):
        if re.search(r"名前|メール|住所|電話|年齢|性別", t):
            add("A24", "the poll asks for personal information")
    return out


# ---- queue, accounts, approvals (private files) ------------------------------------------------------------------------------------------
SECRET_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,40}$")
TOKEN_LIKE = re.compile(r"\bTHAA[A-Za-z0-9]{20,}|\bEAA[A-Za-z0-9]{40,}|\b[A-Za-z0-9_-]{60,}\b")


def validate_accounts(cfg: dict) -> list[str]:
    """accounts.json holds NAMES of secrets, never a token (the file is private, but a token must live only in Secrets / tokens.json)."""
    errs = []
    for a in cfg.get("accounts", []):
        if "token" in a or "access_token" in a:
            errs.append(f"{a.get('id')}: a token value is not allowed here (use token_secret)")
        if not SECRET_NAME.match(str(a.get("token_secret", ""))):
            errs.append(f"{a.get('id')}: token_secret must be the NAME of a secret (UPPER_CASE)")
        for k, v in a.items():
            if isinstance(v, str) and TOKEN_LIKE.search(v):
                errs.append(f"{a.get('id')}: field {k} looks like a token")
        if not a.get("daily_max") or a["daily_max"] > 3:
            errs.append(f"{a.get('id')}: daily_max must be 1-3")
        if "id" not in a or not a.get("categories"):
            errs.append(f"{a.get('id')}: id and categories are required")
    ids = [a.get("id") for a in cfg.get("accounts", [])]
    if len(ids) != len(set(ids)):
        errs.append("duplicate account ids")
    return errs


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


class Publisher:
    """The interface of the part that talks to Threads.  Not implemented on purpose: this task is a dry run (the API is not called)."""
    def publish(self, post: dict) -> str:       # returns the id of the published post
        raise NotImplementedError("the Threads API is not called in the dry run")


@dataclass
class DryRunPublisher(Publisher):
    log: list = field(default_factory=list)

    def publish(self, post: dict) -> str:
        self.log.append(post["id"])
        return "dry-" + str(post["id"])


def dry_run(private: Path, now: datetime, publisher: Publisher | None = None) -> dict:
    """Read the private files, check every queued draft, and 'post' (record) those that are due, approved and clean.  Returns counts and findings (no texts)."""
    publisher = publisher or DryRunPublisher()
    if (private / "PAUSE").exists():
        return {"paused": True, "due": 0, "posted": [], "held": [], "findings": []}
    queue = read_jsonl(private / "queue.jsonl")
    accounts = json.loads((private / "accounts.json").read_text(encoding="utf-8")) if (private / "accounts.json").exists() else {}
    approvals = json.loads((private / "approvals.json").read_text(encoding="utf-8")) if (private / "approvals.json").exists() else None
    terms = json.loads((private / "product_terms.json").read_text(encoding="utf-8")) if (private / "product_terms.json").exists() else []
    errs = validate_accounts(accounts)
    done = [q for q in queue if q.get("state") == "posted"]
    cand = [q for q in queue if q.get("state") in ("approved", "draft")]
    ctx = {"product_terms": terms, "approvals": approvals}
    findings = check_posts_all(cand, accounts, done, ctx) if not errs else []
    bad = {f.item for f in findings}
    posted, held = [], []
    for q in cand:
        if q.get("state") != "approved" or _when(q) > now:
            continue
        if q["id"] in bad or errs:
            held.append(q["id"])
            continue
        publisher.publish(q)
        posted.append(q["id"])
    return {"paused": False, "account_errors": errs, "due": len(posted) + len(held), "posted": posted, "held": held, "findings": findings}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="wadai posts: checks and dry run (never calls Threads)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check-posts", "check-article"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--verbose", action="store_true", help="show the offending snippet (local use only; never in a public log)")
    d = sub.add_parser("dryrun")
    d.add_argument("--private", required=True)
    d.add_argument("--now")
    d.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "check-posts":
        findings = check_posts_all(json.loads(Path(a.file).read_text(encoding="utf-8")))
    elif a.cmd == "check-article":
        findings = check_article(json.loads(Path(a.file).read_text(encoding="utf-8")))
    else:
        r = dry_run(Path(a.private), datetime.fromisoformat(a.now) if a.now else datetime.now())
        print(f"paused={r['paused']} due={r['due']} posted={len(r['posted'])} held={len(r['held'])} account_errors={len(r.get('account_errors', []))}")
        findings = r["findings"]
    for f in findings:
        print(f.line(a.verbose))
    print(f"findings: {len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
