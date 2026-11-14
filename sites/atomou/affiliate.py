"""atomou: the shopping links under a day, a use page, a genre page and the home of one's own days (owner decision 2026-11-14: put every link that fits the page; the money is here).

What is linked: only search pages (Rakuten Ichiba `hb.afl.rakuten.co.jp ... ?pc=<search page>` with the owner's Rakuten ID, Amazon `s?k=<word>&tag=<tag>` with nothing else), the same
forms sites/trend uses (sokuhou-sites/docs/AFFILIATE_RULES.md: the link as provided, no product name / price / image of a mall is kept here).  No product data is stored in the repository.
Every link says PR, carries rel="nofollow sponsored noopener" and target="_blank", and its visible words are a sentence about what is looked for, never an address.

Where nothing is shown (decided by the data, never by a person's eye): a day with `quiet` (grief, disaster, medical, legal), a day with ad_ok false, a genre or category listed in
NEVER (money products, insurance, pensions, gifts of tax, health goods, politics, the world): the owner's rule is "no ads on the sad pages", and the rest keeps away from what the affiliate
programs and the law handle with care.  `links_for` returns "" for all of those, and tests/test_atomou_affiliate.py holds it.

The table WORDS is the one place that says which words are searched for which kind of day: {category or genre: [word, ...]}; {subject} is the name of the subject of the day."""
from __future__ import annotations

import html
from urllib.parse import quote

RAKUTEN_ID = "583f273a.77c989b6.583f273b.0a6a5fff"      # the owner's Rakuten affiliate ID (the same one the other sites use)
AMAZON_TAG = "amazonmacs-22"
REL = 'rel="nofollow sponsored noopener" target="_blank"'

# groups (catalog.GROUPS) and categories that never get a shopping link
NEVER_GROUPS = {"経済・政治", "国際"}
NEVER_CATEGORIES = {"ふるさと納税", "年金・保険", "国民年金", "給付", "制度", "料金", "料金改定", "補助金", "銀行・金融", "日銀・金融", "保険", "金融", "医療", "健康", "薬", "予防接種", "ポリオ",
                    "災害", "防災", "火災予防", "訃報", "命日", "ペット", "お酒", "酒・ドリンク", "飲酒", "禁煙", "介護", "発達支援"}
OPEN_ONLY = {"天気・災害": {"天文", "惑星", "流星群", "月", "日食"}, "健康・くらし": set(), "お金・税金・制度": {"税"}}    # a group with only the listed categories open (an empty set: none)

# category (the finer one) first, then the genre; the words are what a visitor of such a day looks for
WORDS = {
    "資格": ["{subject} 参考書", "{subject} 問題集"],
    "大学入試": ["大学入試 過去問 赤本", "大学受験 参考書"],
    "高校入試": ["高校入試 過去問", "高校受験 参考書"],
    "就活": ["就活 面接 本", "リクルートスーツ"],
    "公務員": ["公務員試験 参考書", "公務員試験 過去問"],
    "奨学金": ["奨学金 本"],
    "年賀状": ["年賀状 印刷", "年賀状 プリンター インク"],
    "セール": ["{subject}"],
    "ポイント": ["{subject}"],
    "駅伝・マラソン": ["ランニングシューズ", "マラソン ウェア"],
    "野球": ["{subject} グッズ"],
    "サッカー": ["{subject} グッズ"],
    "相撲": ["相撲 グッズ"],
    "フィギュア": ["フィギュアスケート グッズ"],
    "音楽": ["{subject} CD", "{subject} Blu-ray"],
    "番組": ["{subject} Blu-ray"],
    "ライブ": ["{subject} グッズ", "ライブ 応援グッズ"],
    "天文": ["双眼鏡 天体観測", "天体望遠鏡"],
    "惑星": ["双眼鏡 天体観測", "天体望遠鏡"],
    "流星群": ["双眼鏡 天体観測", "レジャーシート"],
    "月": ["双眼鏡 天体観測", "天体望遠鏡"],
    "日食": ["日食グラス", "双眼鏡 天体観測"],
    "税": ["確定申告 本"],
    "花火": ["レジャーシート", "折りたたみ 椅子 アウトドア"],
    "イルミネーション": ["使い捨てカイロ", "手袋 スマホ対応"],
    "祭り": ["旅行 ガイドブック"],
    "映画": ["{subject} Blu-ray"],
    "展覧会": ["{subject} 図録"],
    "本・出版": ["{subject}"],
}
GENRE_WORDS = {
    "学校・資格": ["{subject} 参考書"],
    "買い物・料金・セール": ["{subject}"],
    "スポーツ": ["{subject} グッズ"],
    "おでかけ・旅行": ["旅行 ガイドブック", "スーツケース"],
    "スマホ・ネット・アプリ": ["{subject}"],
    "趣味・ゲーム・アニメ": ["{subject} グッズ"],
    "エンタメ・音楽・賞": ["{subject} グッズ"],
    "グルメ・食のイベント": ["{subject}"],
    "イベント・チケット": ["{subject} グッズ"],
    "路線・交通": ["鉄道 グッズ"],
}
# the use pages (/use/<slug>/): words for what the person does there
USE_WORDS = {
    "couple-anniversary": ["記念日 ギフト", "記念日 花束"],
    "exam-university": ["大学入試 過去問 赤本", "大学受験 参考書"],
    "oshi-live": ["推し活 グッズ", "ライブ 応援グッズ"],
    "baby-100days": ["お食い初め 食器", "ベビーフォト 100日"],
    "daily-planner": ["手帳 2027", "卓上カレンダー 2027"],
    "vehicle-passport": ["旅行 ガイドブック"],
}
HOME_WORDS = ["手帳 2027", "卓上カレンダー 2027", "記念日 ギフト"]      # the home of one's own days: what goes with counting days
SOLD_MARK = "探す"


def _kw(template: str, subject: str) -> str:
    return " ".join(template.replace("{subject}", subject).split())


def rakuten_url(word: str) -> str:
    inner = quote("https://search.rakuten.co.jp/search/mall/" + quote(word) + "/", safe="")
    return f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc={inner}"


def amazon_url(word: str) -> str:
    return f"https://www.amazon.co.jp/s?k={quote(word)}&tag={AMAZON_TAG}"


def _block(words: list[str], heading: str, lead: str) -> str:
    def li(fn, label):
        return "<ul>" + "".join(f'<li><a href="{html.escape(fn(w), quote=True)}" {REL}>{label.format(w=html.escape(w))}</a><span class="pr">(PR)</span></li>' for w in words) + "</ul>"
    return (f'<section class="shop" aria-label="関連する商品の検索(広告)"><h2>{html.escape(heading)}<span class="pr">PR</span></h2><p class="small">{html.escape(lead)}</p>'
            + '<p class="small muted">楽天市場の検索ページ</p>' + li(rakuten_url, "楽天市場で「{w}」を探す")
            + '<p class="small muted">Amazonの検索ページ</p>' + li(amazon_url, "Amazonで「{w}」を探す")
            + '<p class="small muted">このブロックのリンクは広告です。購入すると、運営者に報酬が入ることがあります。</p></section>')


def words_for(e: dict) -> list[str]:
    """The words for a day (empty: nothing is shown).  A day marked quiet, off-limits for ads, or in a group / category that never gets a link has none."""
    if e.get("quiet") or e.get("ad_ok") is False:
        return []
    group, cat, subject = e.get("group") or "", e.get("category") or "", (e.get("subject") or "").strip()
    if group in NEVER_GROUPS or cat in NEVER_CATEGORIES:
        return []
    if group in OPEN_ONLY and cat not in OPEN_ONLY[group]:
        return []
    tpl = WORDS.get(cat) or GENRE_WORDS.get(group) or []
    out = []
    for t in tpl:
        if "{subject}" in t and not subject:
            continue
        w = _kw(t, subject)
        if w and w not in out:
            out.append(w)
    return out[:3]


def links_for(e: dict) -> str:
    """The block under a day's page; "" when nothing may be shown."""
    w = words_for(e)
    if not w:
        return ""
    return _block(w, "関連するものを探すなら", "この日に向けて、探すものがあれば、検索ページから探せます。")


def use_links(slug: str) -> str:
    w = USE_WORDS.get(slug) or []
    return _block(w, "この使い方で探すなら", "この使い方に合うものを、検索ページから探せます。") if w else ""


def genre_links(group: str, subjects: list[str]) -> str:
    """The genre page: the words of the genre's most common subjects (no more than three), with the same gates as a day."""
    probe = {"group": group, "category": "", "subject": "", "quiet": False, "ad_ok": True}
    if group in NEVER_GROUPS or group in OPEN_ONLY and not OPEN_ONLY[group]:
        return ""
    words: list[str] = []
    for s in subjects:
        for t in GENRE_WORDS.get(group, []):
            if "{subject}" in t:
                w = _kw(t, s)
                if w not in words and s:
                    words.append(w)
        if len(words) >= 3:
            break
    if not words:
        words = [_kw(t, "") for t in GENRE_WORDS.get(group, []) if "{subject}" not in t][:3]
    probe["words"] = words
    return _block(words[:3], "このジャンルの日に向けて探すなら", "探すものがあれば、検索ページから探せます。") if words else ""


def home_links() -> str:
    return _block(HOME_WORDS, "日数を数えるときに探すなら", "手帳やカレンダー、記念日の贈り物を、検索ページから探せます。")
