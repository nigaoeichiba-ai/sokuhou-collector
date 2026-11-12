"""Writes sites/shiken/content/*.json and site.json from the dates in facts.py / data/ and the pages in pages_*.py.

    python -m sites.shiken.gen         (from sokuhou-collector/)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .common import CHECKED
from .sources import SOURCES

SITE = Path(__file__).resolve().parents[1]


def all_pages() -> list[dict]:
    from . import pages_hub, pages_exam, pages_nyushi, pages_deep
    out = []
    for m in (pages_hub, pages_exam, pages_nyushi, pages_deep):
        out += m.pages()
    from .extra import EXTRA, EXTRA_METHOD_TABLE
    for p in out:
        if p["path"] in EXTRA and p["path"] != "/cbt/":
            p["sections"] = p["sections"][:-1] + EXTRA[p["path"]] + p["sections"][-1:] if p["sections"][-1]["h2"].startswith("最終確認") else p["sections"] + EXTRA[p["path"]]
        if p["path"] == "/method/":
            p["sections"][2]["table"] = EXTRA_METHOD_TABLE
    from . import pages_v2, pages_takken, pages_features, pages_lists, pages_articles
    new = {p["path"]: p for p in (pages_v2.home(), pages_takken.takken(), pages_features.goukaku_ritsu(), pages_features.cbt(), pages_features.yomimono(), pages_features.tokushu_nyushi(), *pages_articles.pages())}
    out = [new.pop(p["path"], p) for p in out] + list(new.values())
    out = [pages_lists.restyle(p) for p in out]
    from .pages_exam import shop_section
    for p in out:
        p["sections"] = [s for s in p["sections"] if s]
        if p["path"] in SHOP_PAGES and not any("PR" in str(x.get("h2", "")) for x in p["sections"]):
            at = next((i for i, x in enumerate(p["sections"]) if str(x.get("h2", "")).startswith("最終確認")), len(p["sections"]))
            p["sections"].insert(at, shop_section(*SHOP_PAGES[p["path"]]))
    return [finalize(p) for p in out]


# 2026-11-13: the exam pages without a study-book search link get one (Rakuten / Amazon search pages, PR).  path -> (exam name, search words)
SHOP_PAGES = {"/boki/": ("日商簿記", "日商簿記 テキスト"), "/boki-net/": ("簿記のネット試験", "簿記 ネット試験 問題集"), "/fp/": ("FP技能検定", "FP技能検定 テキスト"),
              "/eiken/": ("英検", "英検 過去問"), "/kaigo-fukushi/": ("介護福祉士", "介護福祉士 参考書"), "/kangoshi/": ("看護師国家試験", "看護師国家試験 参考書"),
              "/sharoshi/": ("社会保険労務士", "社会保険労務士 テキスト"), "/minkan/": ("TOEIC", "TOEIC 公式問題集"), "/komuin/": ("公務員試験", "公務員試験 参考書"),
              "/kyotsu/": ("共通テスト", "共通テスト 過去問"), "/koko/": ("公立高校入試", "高校入試 過去問")}


CLOSING = "最終的な日程は、主催団体の公式発表でご確認ください。日程は変更されることがあります。申し込む前に、必ず確かめてください。"   # kept only by the pages of KEEP_NOTES
KEEP_NOTES: set = set()   # empty since 2026-11-09: every page has its added sentence (the mechanism stays for a page that falls under the limit)

# the desk's added sentences (sites/shiken/additions/<slug>.md, written by Muse, put in word for word): the slug -> the heading of the section after which the sentence stands
ADD_AFTER = {"boki-net": "決まり方の違い", "flow": "いつ、何をするか", "kokkoritsu": "出願期間は大学ごとに決まる", "komuin": "公表されている日程",
             "kyotsu-tsuishi": "本試験を受けられなかったときの順番", "kyotsu": "これから受験生が確認すること", "minkan": "TOEIC L&Rの公開テスト", "nendo": "見落とさない方法",
             "nyushi": "2027年1月から3月の主な日程", "postmark": "意味の違い", "results": "発表の時刻と方法", "yama": "月別の件数"}
HELD: set = set()   # a sentence of the desk that waits for a check


def added_sentence(slug: str) -> str:
    text = (SITE / "additions" / f"{slug}.md").read_text(encoding="utf-8")
    body = text.split("## 追加文（このまま入れてください）", 1)[1]
    return " ".join(l.strip() for l in body.strip().splitlines() if l.strip())

GENERAL_NOTES = {"日程は変わることがあります。", "日程が変わることがあります。"}   # said by every page: the footer has the one sentence
DROP = re.compile(r"(日程と金額の|日付の)?確認日は2026年11月3日です。|申込の前に、次の公式ページで[^。]*確かめてください。|申込の前に、必ず公式ページで確かめてください。")


def finalize(p: dict) -> dict:
    """The owner's rule (2026-11-03): no source URL, no 'checked on' day per row, no list of official links on a page.  What stays: the page's update day,
    one closing sentence on every page, and the method page.  (The dates are still read from the primary sources when they are made.)"""
    p.pop("sources", None)
    secs = []
    for s in p["sections"]:
        s = dict(s)
        if re.search(r'href="https?://(?!calendar\.google\.com/|px\.a8\.net/|hb\.afl\.rakuten\.co\.jp/|www\.amazon\.co\.jp/s\?)', s.get("html", "")):
            s.pop("html")
        s["paras"] = [t for t in (DROP.sub("", t).strip() for t in s.get("paras", [])) if t]
        secs.append(s)
    slug = p["path"].strip("/")
    if slug in ADD_AFTER and slug not in HELD:
        out = []
        for sec_ in secs:
            out.append(sec_)
            if sec_.get("h2", "").startswith(ADD_AFTER[slug]):
                out.append({"paras": [added_sentence(slug)]})
        assert len(out) == len(secs) + 1, f"{slug}: the section {ADD_AFTER[slug]!r} is not on the page"
        secs = out
    # the owner's rule (2026-11-09): the site-wide notes (where the dates come from, when they were counted, "check the official page") are said once, in the footer.
    # What stays: a note that belongs to one exam ("受験料は、受験する商工会議所の案内で確かめてください").
    if p["path"] in KEEP_NOTES:
        # TEMPORARY (2026-11-09): these pages would fall under the 1,200-character limit of a page that is indexed without the notes; they keep the old closing notes
        # until the desk's added sentences arrive (the desk's request: 注記整理_追加文依頼_2026-11-09.md); then the page leaves this set and the notes go.
        p["sources_style"] = "credit"
        last = secs[-1]
        if last.get("h2") == "最終確認は公式で":
            last["paras"] = last["paras"] + [CLOSING]
        else:
            secs.append({"h2": "最終確認は公式で", "paras": [CLOSING]})
    else:
        out = []
        for s in secs:
            if s.get("h2") == "最終確認は公式で":
                s["paras"] = [t for t in s.get("paras", []) if t not in GENERAL_NOTES]
                if not (s["paras"] or s.get("html") or s.get("table")):
                    continue
            out.append(s)
        secs = out
    p["sections"] = secs
    return p


def write(root: Path = SITE) -> int:
    pages = all_pages()
    content = root / "content"
    for f in content.glob("*.json"):
        f.unlink()
    for p in pages:
        p.setdefault("updated", CHECKED)
        slug = p["path"].strip("/").replace("/", "-") or "home"
        (content / f"{slug}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    site = json.loads((root / "site.json").read_text(encoding="utf-8"))
    site["sources"] = {}
    site["sources_style"] = "stamp"
    site["credits"] = ["各試験団体・省庁・教育委員会の発表と、信頼できる報道・関連サイトの情報をもとに作成"]
    site["updated"] = CHECKED
    site.update({
        "nav": [["日程の一覧", "/schedule/", "/schedule/"], ["締切が近い順", "/deadlines/", "/deadlines/"], ["入試", "/nyushi/", "/nyushi/"],
                ["特集", "/yomimono/", "/yomimono/"]],
        "footer_html": "日程は、各試験団体・省庁・教育委員会の発表や、報道・関連サイトの情報をもとにしています。最終的な日程は、主催団体の公式発表でご確認ください。",
        "purpose": "資格試験と入学試験の、申込・出願の期間、試験日、合格発表日を、確かめた日付で表示すること。受験する方が、締切を見落とさないための道具です。",
        "update_text": "試験団体が日程を発表したら、公式ページで日付を確かめて入れ替え、各ページの最終更新日を書き換えます。年度が替わるたびに、全ページの日付を公式ページから取り直します。直した内容は「訂正と更新の記録」に残します。",
        "disclaimer": [
            "日程は、試験団体や教育委員会が変更することがあります。申し込む前に、必ず公式ページで最新の内容を確認してください。",
            "このサイトは、日付と制度の事実を伝えるものです。個々の受験について、出願先や受験資格の判断はしません。",
        ],
        "method": [
            "試験団体・省庁・教育委員会の公式ページを開き、日付を読み取って、表に表示します。曜日と「あと何日」は、日付から自動で計算されます。",
            "公式ページに載っていない日程は、推測で補いません。その試験については、次の回が未発表であることだけが表示されます。",
            "各団体の表や文章は写していません。日付や金額という事実だけが、当サイトの表に表示されます。",
        ],
    })
    (root / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(pages)


def stale() -> list[str]:
    """The dates the prose was written around that have passed since CHECKED (the pages say 'next' / 'coming'): the facts need the yearly (or weekly) re-reading."""
    from .common import CHECKED, TODAY, d
    from .facts import EVENTS, TOEIC
    out = [f"{who} {kind} {iso}" for who, g, kind, iso, src, note in EVENTS if d(CHECKED) <= d(iso) < TODAY]
    out += [f"TOEIC {x} {iso}" for row in TOEIC for x, iso in zip(("試験日", "申込開始", "申込締切", "認定証"), row) if d(CHECKED) <= d(iso) < TODAY]
    return out


if __name__ == "__main__":
    print(write(), "pages")
