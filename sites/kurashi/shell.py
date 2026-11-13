"""The page frame of the 2026-11-13 design (the owner's template 「暮らしの準備と手続き」): header, footer, hero, the guide blocks, the home page, the saved / search pages, data.js.

Nothing here decides a fact.  Every date, number and sentence of a page comes from sites/kurashi/content/*.json (the pages), sites/kurashi/guides/*.json (the checked guides: the
template's eleven articles with the corrections of 2026-11-13, and five short ones that only feed the calendar's dialogs) and site.json (the deadline catalog).  The words that are the
parts' own labels are the constants below.  hooks.py calls these functions from its `post` step and replaces the plain pages of sokuhou/newsite.py with them.

The browser side is assets/t/*.js (the template's calendar, saved list and search); assets/t/data.js is written here from the same sources, so the calendar and the pages cannot disagree.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_NAME = "暮らしの準備と手続き"
TAGLINE = ("いつまでに、", "何を用意すればいいかをご案内します。")
WD = "月火水木金土日"

# path -> (illustration, colour of the picture's panel, small heading above the title)
ART = {
    "/moving/": ("moving", "sky", "引っ越し・住まいの手続き"), "/moving/tenshutsu/": ("moving", "sky", "引っ越し・住まいの手続き"), "/moving/menkyo-sha/": ("moving", "sky", "引っ越し・住まいの手続き"),
    "/shin-seikatsu/": ("marriage", "cream", "新生活の手続き"), "/life/birth/": ("birth", "peach", "出産・子育ての手続き"), "/life/taishoku/": ("retire", "mint", "退職・転職の手続き"),
    "/life/kekkon/": ("marriage", "cream", "結婚・新生活の手続き"), "/life/kaigo/": ("care", "lilac", "家族の介護の手続き"), "/life/shibo/": ("bereavement", "sky", "家族が亡くなったときの手続き"),
    "/life/": ("moving", "cream", "人生の節目の手続き"), "/nenmatsu-chosei/": ("tax", "mint", "仕事・税金の手続き"), "/iryouhi-koujo/": ("medical", "lilac", "医療費控除"),
    "/kakutei-shinkoku/": ("tax", "mint", "確定申告"), "/kakutei-shinkoku/junbi/": ("tax", "mint", "確定申告"), "/kakutei-shinkoku/hitsuyo/": ("tax", "mint", "確定申告"),
    "/kakutei-shinkoku/kanpu/": ("tax", "mint", "確定申告"), "/kakutei-shinkoku/furusato/": ("donation", "cream", "ふるさと納税"), "/furusato/deadline/": ("donation", "cream", "ふるさと納税"),
    "/furusato/one-stop/": ("donation", "cream", "ふるさと納税"), "/nengajo/": ("calendar", "peach", "年賀状"), "/nenmatsu-nenshi/": ("calendar", "sky", "年末年始"),
    "/kafun/": ("care", "mint", "花粉症の準備"), "/method/": ("calendar", "cream", "期限の数え方"), "/month/": ("calendar", "mint", "月ごとの準備"),
}
MONTH_ART = ("calendar", "cream", "月ごとの準備")

# the catalog event -> the guide whose dialog the calendar opens, and the kind the calendar shows it as (prep / deadline / boundary = the year's end)
EVENT_GUIDE = {"nengajo-hikiuke": "nengajo", "nengajo-motojitsu": "nengajo", "nengajo-hanbai-end": "nengajo", "gyosei-saigo-heijitsu": "holiday", "gyosei-yasumi": "holiday",
               "nenmatsu-shime": "furusato-deadline", "kanpu-start": "kanpu", "onestop-henko": "donation", "kyotsu-honshiken": "kyotsu", "shinkoku-start": "kakutei-shinkoku",
               "shinkoku-end": "kakutei-shinkoku"}
EVENT_KIND = {"onestop-henko": "deadline", "shinkoku-end": "deadline", "nengajo-hanbai-end": "deadline", "nenmatsu-shime": "boundary", "gyosei-saigo-heijitsu": "boundary",
              "gyosei-yasumi": "boundary"}
EVENT_DESC = {
    "nengajo-hikiuke": "2027年用の年賀状の引き受けが始まります。日本郵便の発表(2026年8月31日)による日です。",
    "nengajo-motojitsu": "元日に届けるための差し出し日の目安です。日本郵便は、この日までに出された年賀状を元日にお届けするよう取り組むと発表しています。",
    "nengajo-hanbai-end": "年賀はがきの販売の最終日です。販売は2026年11月2日から2027年1月15日までです。",
    "gyosei-saigo-heijitsu": "国の行政機関が、年内に開いている最後の平日です。翌日から1月3日までは、国の行政機関の休日です。",
    "gyosei-yasumi": "国の行政機関の年末年始の休み(12月29日から1月3日)が始まります。市区町村の休みは条例で決まるので、窓口ごとの案内を確かめてください。",
    "nenmatsu-shime": "ふるさと納税と医療費は、この日までに支払った分が2026年分の対象です。申告の期限とは別の日です。",
    "kanpu-start": "令和8年分の還付申告を、この日から提出できます。確定申告の期間の初日とは別の日です。",
    "onestop-henko": "ワンストップ特例の申請後に住所や氏名が変わったときの、変更届の期限です。多くの自治体は、申請書の締切も1月10日(必着)としています。寄附先の案内で確かめてください。",
    "kyotsu-honshiken": "令和9年度の大学入学共通テストの本試験の初日です。試験は2日間です。",
    "shinkoku-start": "令和8年分の確定申告の期間が始まります。",
    "shinkoku-end": "令和8年分の確定申告と納税の期限(原則)です。",
}
HOME_EVENTS = [
    ("moving", "引っ越し", "moving", "sky", "/moving/", "住所変更と契約を、順番に"),
    ("birth", "出産・子育て", "birth", "peach", "/life/birth/", "家族が増えたら、届けること"),
    ("retire", "退職・転職", "retire", "mint", "/life/taishoku/", "仕事が変わる前後の保険・年金"),
    ("marriage", "結婚・新生活", "marriage", "cream", "/life/kekkon/", "新しい暮らしの届出と変更"),
    ("care", "家族の介護", "care", "lilac", "/life/kaigo/", "相談できる窓口を知ることから"),
    ("bereavement", "家族が亡くなったとき", "bereavement", "sky", "/life/shibo/", "急ぐ手続きから、ひとつずつ"),
    ("tax", "確定申告・年末調整", "tax", "mint", "/kakutei-shinkoku/", "期間・書類・還付申告の日付"),
    ("donation", "ふるさと納税・医療費", "donation", "cream", "/furusato/deadline/", "年内の締めと、申告の期限"),
    ("nengajo", "年賀状・年末年始", "calendar", "peach", "/nengajo/", "年賀状の日程と、役所の休み"),
]
NAV = [("/", "カレンダー"), ("/life/", "出来事から探す"), ("/month/", "月から探す"), ("/kakutei-shinkoku/", "確定申告")]
MOBILE_NAV = NAV + [("/search/", "検索"), ("/nengajo/", "年賀状"), ("/method/", "期限の数え方")]
FOOT_NAV = [("/about/", "運営者情報"), ("/method/", "期限の数え方"), ("/privacy/", "プライバシー"), ("/contact/", "お問い合わせ"), ("/search/", "検索")]

PR = "【PR】"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def md(x: date) -> str:
    return f"{x.month}月{x.day}日({WD[x.weekday()]})"


def jp(x: date) -> str:
    return f"{x.year}年{md(x)}"


# ---------------------------------------------------------------- the pictures (the template's code-native illustrations)
_ILL: dict[str, str] = {}
_SPARKLE = ""


def _load_illustrations() -> None:
    global _SPARKLE
    src = (ROOT / "assets" / "t" / "illustrations.js").read_text(encoding="utf-8")
    plant = re.search(r"const plant=`(.*?)`;", src, re.S).group(1)
    _SPARKLE = re.search(r"const sparkle=`(.*?)`;", src, re.S).group(1)
    body = re.search(r"const drawings=\{(.*?)\n\};", src, re.S).group(1)
    for m in re.finditer(r"\n\s*(\w+):`(.*?)`(?:,|$)", "\n" + body, re.S):
        _ILL[m.group(1)] = m.group(2).replace("${plant}", plant)


def illustration(name: str) -> str:
    if not _ILL:
        _load_illustrations()
    return ('<svg class="spot-illustration" viewBox="0 0 200 150" fill="none" stroke="#30465f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
            f'focusable="false"><ellipse cx="99" cy="132" rx="76" ry="5" fill="#e2dfce" opacity=".32" stroke="none"/>{_SPARKLE}{_ILL.get(name) or _ILL["calendar"]}</svg>')


def short(t: str, n: int = 22) -> str:
    """a label for a list of links: a long heading is cut (the full text is the heading itself on the page)"""
    return t if len(t) <= n else t[:n - 1] + "…"


def phrases(text: str) -> str:
    """a title in phrases that do not break in the middle (the template's heading-phrase): cut after 。 、 and spaces; a phrase of more than 13 characters is left to wrap"""
    parts = [x for x in re.split(r"(?<=[。、！？ 　])", text) if x]
    out = []
    for x in parts:
        out.append(f'<span class="heading-phrase">{e(x)}</span>' if len(x.strip()) <= 13 else e(x))
    return "".join(out)


# ---------------------------------------------------------------- the data the pages and the browser share
def load_guides() -> tuple[dict, dict]:
    g = {}
    for f in sorted((ROOT / "guides").glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        g[d["id"]] = d
    return g, json.loads((ROOT / "guides" / "_site.json").read_text(encoding="utf-8"))


def guide_of_page(guides: dict) -> dict[str, dict]:
    return {g["path"]: g for g in guides.values() if not g.get("light")}


def category_of(g: dict, tsite: dict) -> dict:
    return next(c for c in tsite["categories"] if c["id"] == g["categories"][0])


def data_js(guides: dict, tsite: dict, spec: dict, pages_index: dict, today: date) -> str:
    gs = {}
    for k, g in guides.items():
        d = {x: g[x] for x in ("id", "status", "categories", "title", "short", "icon", "topic", "audience", "summary", "when", "where", "documents", "steps", "source",
                               "calendar", "datedEvents") if x in g}
        d["stepTitles"] = g.get("stepTitles") or []
        d["url"] = g["path"]
        for x in ("planner", "factCheck"):
            if g.get(x):
                d[x] = g[x]
        d["datedEvents"] = list(d.get("datedEvents", []))
        gs[k] = d
    for c in spec.get("deadlines", []):
        gid = EVENT_GUIDE[c["id"]]
        gs[gid]["datedEvents"].append({"id": c["id"], "date": c["date"], "title": c["name"], "description": EVENT_DESC[c["id"]], "kind": EVENT_KIND.get(c["id"], "prep")})
    cats = [{"id": i, "name": n, "icon": icon, "color": col, "url": url, "homeTitle": n, "homeSummary": s, "keys": []} for i, n, icon, col, url, s in HOME_EVENTS]
    consts = {
        "CALENDAR_RANGE": tsite["calendarRange"], "LEGACY_DOCUMENT_CHECKS": {}, "LEGACY_PLANNER_ITEMS": {}, "GUIDES": gs, "CATEGORIES": cats, "SOURCES": tsite["sources"],
        "CHECKED_DATE": tsite["checkedDate"], "MONTH_NAMES": tsite["monthNames"], "TOPICS": tsite["topics"], "HOLIDAYS": tsite["holidays"], "PAGES": pages_index,
    }
    out = "// Generated by sites/kurashi/shell.py from content/, guides/ and site.json. Do not edit this file.\n"
    out += "\n".join(f"export const {k}={json.dumps(v, ensure_ascii=False, separators=(',', ':'))};" for k, v in consts.items()) + "\n"
    out += CALENDAR_RECORDS_JS
    return out


CALENDAR_RECORDS_JS = """const calendarRecords=(GUIDES,month)=>{
  if(!/^\\d{4}-(0[1-9]|1[0-2])$/.test(month))throw Error('month: '+month);
  const m=Number(month.slice(-2));
  return Object.entries(GUIDES).flatMap(([guide,g])=>[
   ...g.calendar.filter(e=>e.month===m).map(e=>({id:`${month.slice(0,4)}-${guide}-${e.id}`,date:`${month}-${String(e.day).padStart(2,'0')}`,title:e.title,description:g.summary,guide,topic:g.topic,kind:'prep'})),
   ...g.datedEvents.filter(e=>e.date.startsWith(month+'-')).map(e=>({...e,guide,topic:g.topic}))
  ]).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
};
export const recordsForMonth=month=>calendarRecords(GUIDES,month);
"""


def pages_index(content: list[dict], guides: dict) -> dict:
    """what the search page looks in: the address, the title, one sentence, and the text of every page"""
    out = {}
    for p in content:
        if p["path"] == "/":
            continue
        text = " ".join([p["title"], p["h1"], p["description"], *[s.get("h2") or "" for s in p["sections"]], *[t for s in p["sections"] for t in s.get("paras", [])]])
        g = next((x for x in guides.values() if x["path"] == p["path"] and not x.get("light")), None)
        if g:
            text += " " + g["title"] + g["short"] + g["summary"] + "".join(d["text"] for d in g["documents"]) + "".join(g["steps"])
        key = re.sub(r"[^a-z0-9]+", "-", p["path"].strip("/")).strip("-")
        out[key] = {"title": p["h1"] if len(p["h1"]) < 40 else p["title"], "summary": p["description"], "url": p["path"], "text": text}
    return out


# ---------------------------------------------------------------- the frame
def brand() -> str:
    return ('<span class="brand-icon"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2m-8 3h2"/></svg></span>'
            f'<span><span class="brand-name"><span>暮らしの</span><span>準備と手続き</span></span><small class="brand-tagline"><span>{TAGLINE[0]}</span><span>{TAGLINE[1]}</span></small></span>')


def header(path: str, home: bool = False) -> str:
    def cur(p: str) -> str:
        on = path == "/" if p == "/" else path.startswith(p)
        if p == "/life/":
            on = path.startswith(("/life/", "/moving/", "/shin-seikatsu/"))
        if p == "/kakutei-shinkoku/":
            on = path.startswith(("/kakutei-shinkoku/", "/nenmatsu-chosei/", "/iryouhi-koujo/", "/furusato/"))
        return ' class="is-current" aria-current="page"' if on else ""
    desk = "".join(f'<a href="{p}"{cur(p)}>{t}</a>' for p, t in NAV)
    mob = "".join(f'<a href="{p}">{t}</a>' for p, t in MOBILE_NAV)
    if home:      # the home page's own script (assets/t/app.js) drives the saved count and the menu
        saved = ('<button class="saved-trigger icon-label" data-action="show-saved" aria-label="あとで見る"><span data-icon="bookmark"></span><span class="saved-label" data-t="あとで見る"></span>'
                 '<span class="count" id="saved-count">0</span></button>')
        menu = ('<button class="mobile-menu icon-button" data-action="menu" aria-expanded="false" aria-controls="mobile-navigation" aria-label="メニューを開く"><span data-icon="menu"></span></button>')
        navid = "mobile-navigation"
    else:
        saved = '<a class="saved-trigger icon-label" href="/saved/" aria-label="あとで見る"><span class="saved-label" data-t="あとで見る"></span><span class="count" data-saved-count>0</span></a>'
        menu = '<button class="mobile-menu icon-button" data-menu aria-controls="page-menu" aria-expanded="false" aria-label="メニューを開く">☰</button>'
        navid = "page-menu"
    return (f'<header class="site-header wrap"><a class="brand" href="/" aria-label="{SITE_NAME} トップ">{brand()}</a><nav class="desktop-nav" aria-label="メインメニュー">{desk}</nav>'
            f'{saved}{menu}</header><nav id="{navid}" class="mobile-navigation" aria-label="スマホのメニュー" hidden>{mob}</nav>')


def footer(foot_note: str = "") -> str:
    nav = "".join(f'<a href="{p}">{t}</a>' for p, t in FOOT_NAV)
    return ('<div class="footer-town"><img src="/assets/t/town-panorama-v2.webp" alt="" width="2172" height="724" loading="lazy"></div>'
            f'<footer class="site-footer wrap"><a class="brand" href="/">{brand()}</a><nav aria-label="フッター">{nav}</nav>'
            f'<small>&copy; {SITE_NAME}</small></footer>{foot_note}<p class="page-status" role="status" aria-live="polite" id="page-status"></p>')


def crumbs(items: list[tuple[str, str | None]]) -> str:
    lis = "".join(f'<li><a href="{e(h)}">{e(t)}</a></li>' if h else f'<li><span aria-current="page">{e(t)}</span></li>' for t, h in items)
    return f'<nav class="breadcrumbs crumbs" aria-label="パンくずリスト"><ol><li><a href="/">ホーム</a></li>{lis}</ol></nav>'


def css_links(ver: str) -> str:
    return "".join(f'<link rel="stylesheet" href="/assets/t/{n}.css?v={ver}">' for n in ("styles", "illustrated", "readability", "pages", "hierarchy")) + \
           f'<link rel="stylesheet" href="/assets/kurashi.css?v={ver}">'


def rewrap(old: str, main: str, *, path: str, ver: str, body_class: str, modules: str = "pages", noindex: bool = False, foot_note: str = "", with_tools: str = "",
           head_more: str = "", home: bool = False) -> str:
    """the head of the page that sokuhou/sitekit.py wrote (title, description, canonical, share tags, structured data, icons, the AdSense tag) kept as it is, the style sheet and the
    frame replaced"""
    m = re.search(r"<head>\n(.*?)</head>", old, re.S)
    head = re.sub(r'<link rel="stylesheet" href="/assets/style\.css[^"]*">\n?', "", m.group(1))
    if noindex and 'name="robots"' not in head:
        head = '<meta name="robots" content="noindex,nofollow">\n' + head
    head += '<meta name="theme-color" content="#fffdf7">\n' + css_links(ver) + "\n" + head_more
    if modules:
        head += f'<script type="module" src="/assets/t/{modules}.js?v={ver}"></script>\n'
    return (f'<!doctype html>\n<html lang="ja">\n<head>\n{head}</head>\n<body class="{body_class}" data-cat="calendar">\n'
            f'<a class="skip-link" href="#content">本文へ移動</a>\n{header(path, home)}\n<main id="content">\n{main}\n</main>\n{footer(foot_note)}\n{with_tools}</body>\n</html>\n')


# ---------------------------------------------------------------- the parts of a page
def deadline_cards(events: list[dict], bundle: str | None, ctx) -> str:
    if not events:
        return ""
    cards = ""
    for c in events:
        d = date.fromisoformat(c["date"])
        desc = EVENT_DESC.get(c["id"], "")
        cards += (f'<div class="deadline-card"><h4>{e(c["name"])}</h4><p class="deadline-when">{jp(d)}<span class="left"> ・あと{{days:{c["date"]}}}日</span></p>'
                  f'<p>{e(desc)}</p><p><a class="secondary-button cal-b" href="/calendar/{c["id"]}.ics" download>カレンダーに登録</a></p></div>')
    more = (f'<p><a class="text-button" href="/{bundle}" download>まとめて登録</a></p>' if bundle else "") + '<p class="small-note">通知は前日の午前9時です。</p>'
    return f'<div class="deadline-summary cal"><h3>日付で確かめる</h3>{cards}{more}</div>'


def guide_deadlines(g: dict, tsite: dict) -> str:
    if not g.get("deadlines"):
        return ""
    cards = "".join(f'<div class="deadline-card"><h4>{e(d["label"])}</h4><p class="deadline-when">{e(d["when"])}</p><p>{e(d["note"])}</p>{citations([d["source"]], tsite)}</div>' for d in g["deadlines"])
    return f'<div class="deadline-summary"><h3>先に確認したい期限</h3>{cards}</div>'


def citations(ids: list[str], tsite: dict) -> str:
    return '<p class="article-citations">参照:' + " ／ ".join(f'<a href="{e(tsite["sources"][i]["url"])}" target="_blank" rel="noopener noreferrer">{e(tsite["sources"][i]["name"])}</a>' for i in ids) + "</p>"


def official_label(s: dict) -> str:
    name = s["name"]
    i = name.find("｜")
    if i < 0:
        return f'<span class="official-link-label"><span class="official-title"><span class="official-phrase">{e(name)}</span></span></span>'
    agency, title = name[:i + 1], name[i + 1:]
    ph = s.get("phrases") or [title]
    return (f'<span class="official-link-label"><span class="official-agency">{e(agency)}</span><span class="official-title">'
            + "".join(f'<span class="official-phrase">{e(t)}</span>' for t in ph) + "</span></span>")


def official_list(g: dict | None, p: dict, spec: dict, tsite: dict) -> str:
    """links to the official pages: the guide's own list, and the sources of the page that are pages of an office (the statutes stay out of the text, owner 2026-11-03)"""
    items = []
    seen = set()
    if g:
        for i in g["source"]:
            s = tsite["sources"][i]
            seen.add(s["url"])
            items.append((s["url"], official_label(s), s.get("checkedAt") or g["factCheck"]["checkedAt"]))
    for i in p.get("sources", []):
        s = spec["sources"].get(i)
        if not s or s["org"].startswith("e-Gov") or s["url"] in seen:
            continue
        seen.add(s["url"])
        items.append((s["url"], f'<span class="official-link-label"><span class="official-agency">{e(s["org"])}｜</span><span class="official-title"><span class="official-phrase">{e(s["table"])}</span></span></span>', s["fetched"]))
    if not items:
        return ""
    lis = "".join(f'<li><a href="{e(u)}" target="_blank" rel="noopener noreferrer">{lab} <span class="official-link-icon" aria-hidden="true">↗</span></a><span>公式サイト・別のタブで開きます ／ 確認日：{e(d)}</span></li>' for u, lab, d in items)
    return lis


def section_block(n: int, s: dict, table_html, count: int) -> str:
    out = []
    if s.get("h2"):
        out.append(f'<header class="article-section-heading"><h2>{e(s["h2"])}</h2></header>')
    out.extend(f"<p>{e(t)}</p>" for t in s.get("paras", []))
    if s.get("table"):
        out.append(table_html(s["table"]))
    if s.get("html"):
        out.append(s["html"])
    return f'<section id="s{n}" class="article-section legacy-section">{"".join(out)}</section>'


def faq_html(g: dict) -> str:
    return "".join(f"<details><summary>{e(f['question'])}</summary><p>{e(f['answer'])}</p></details>" for f in g.get("faq", []))


def faq_ld(g: dict) -> str:
    d = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": f["question"], "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}} for f in g.get("faq", [])]}
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def read_minutes(p: dict, g: dict | None) -> int:
    n = sum(len("".join(s.get("paras", []))) for s in p["sections"])
    if g:
        n += len(json.dumps([g["summary"], g["steps"], g.get("sections"), g.get("faq")], ensure_ascii=False))
    return max(3, -(-n // 450))


def eyebrow_of(p: dict, g: dict | None) -> str:
    if p["path"] in ART:
        return ART[p["path"]][2]
    if p["path"].startswith("/month/"):
        return MONTH_ART[2]
    return "暮らしの手続き"


def art_of(p: dict) -> tuple[str, str]:
    a = ART.get(p["path"]) or MONTH_ART
    return a[0], a[1]


def crumb_items(p: dict, by_path: dict) -> list[tuple[str, str | None]]:
    chain = []
    q = p
    while q.get("parent"):
        q = by_path[q["parent"]]
        if q["path"] != "/":
            chain.append((CRUMB.get(q["path"]) or q["title"], q["path"]))
    return list(reversed(chain)) + [(CRUMB.get(p["path"]) or p["title"], None)]


CRUMB = {"/month/": "月別のやること", "/life/": "人生の節目の手続き", "/moving/": "引っ越し手続き", "/kakutei-shinkoku/": "確定申告", "/nengajo/": "年賀状", "/nenmatsu-chosei/": "年末調整",
         "/furusato/deadline/": "ふるさと納税の期限", "/furusato/one-stop/": "ワンストップ特例", "/kakutei-shinkoku/furusato/": "ふるさと納税と確定申告", "/iryouhi-koujo/": "医療費控除",
         "/nenmatsu-nenshi/": "役所の年末年始", "/kakutei-shinkoku/junbi/": "確定申告の準備", "/kakutei-shinkoku/hitsuyo/": "確定申告が必要な人", "/kakutei-shinkoku/kanpu/": "還付申告",
         "/moving/tenshutsu/": "転出届・転入届", "/moving/menkyo-sha/": "車検証・免許証", "/shin-seikatsu/": "新生活", "/kafun/": "花粉症", "/method/": "期限の数え方",
         "/life/birth/": "出産・子育て", "/life/taishoku/": "退職・転職", "/life/kekkon/": "結婚", "/life/shibo/": "家族が亡くなったとき", "/life/kaigo/": "介護",
         "/month/1/": "1月", "/month/2/": "2月", "/month/3/": "3月", "/month/11/": "11月", "/month/12/": "12月"}


def render_page(p: dict, ctx) -> tuple[str, str]:
    """(the <main> content, extra head markup) of a content page"""
    g = ctx.page_guide.get(p["path"])
    path = p["path"]
    icon, color = art_of(p)
    lead = p.get("_answer_marked") or p.get("answer") or ""
    ev, bundle = ctx.per_page.get(path, ([], None))
    updated = date.fromisoformat(p["updated"])
    meta = f'<span>最終更新日：{updated.year}年{updated.month}月{updated.day}日</span>'
    if g:
        meta += f'<span>出典確認日：{e(g["factCheck"]["checkedAt"])}</span>'
    meta += f'<span>読む目安：約{read_minutes(p, g)}分</span>'
    save = f'<button class="secondary-button" data-save-guide="{g["id"]}" aria-pressed="false">あとで読む</button>' if g else ""
    tools = f'<div class="article-tools">{save}<button type="button" class="text-button" data-print hidden>印刷する</button></div>'
    hero = (f'<div class="article-masthead"><header class="article-hero wrap"><div><p class="eyebrow">{e(eyebrow_of(p, g))}</p><h1>{phrases(p["h1"])}</h1>'
            f'<p class="article-lead">{e(lead)}</p><div class="article-meta">{meta}</div>{tools}</div>'
            f'<div class="article-art {color}">{illustration(icon)}</div></header></div>')
    # --- the body
    main = []
    if g:
        facts = (f'<dl><div class="fact-row"><dt>こんな方へ</dt><dd>{e(g["audience"])}</dd></div><div class="fact-row"><dt>いつまでに</dt><dd>{e(g["when"])}</dd></div>'
                 f'<div class="fact-row"><dt>確認する窓口</dt><dd>{e(g["where"])}</dd></div></dl>')
        main.append('<section class="at-a-glance"><header class="overview-heading"><p class="eyebrow">先に、ここを確かめましょう</p><h2>この手続きの<span class="heading-phrase">ポイント</span></h2></header>'
                    + facts + guide_deadlines(g, ctx.tsite) + deadline_cards(ev, bundle, ctx) + "</section>")
    elif ev:
        main.append('<section class="at-a-glance"><header class="overview-heading"><p class="eyebrow">先に、ここを確かめましょう</p><h2>このページの<span class="heading-phrase">期限</span></h2></header>'
                    + deadline_cards(ev, bundle, ctx) + "</section>")
    toc = [("preparation", "用意しておきたいもの"), ("steps", "準備と手続きの進め方")] if g else []
    legacy = [(f"s{n}", s["h2"]) for n, s in enumerate(p["sections"]) if s.get("h2")]
    anchors = toc + legacy
    if g:
        anchors += [("official", "公式の確認先"), ("article-faq", "よくある質問")]
    elif ctx.official.get(path):
        anchors += [("official", "公式の確認先")]
    if len(anchors) >= 3:
        main.append('<nav class="article-toc" aria-label="目次"><h2>このページでわかること</h2><ol>' + "".join(f'<li><a href="#{a}">{e(short(t))}</a></li>' for a, t in anchors) + "</ol></nav>")
    if g:
        docs = "".join(f'<label class="document-item"><input type="checkbox" data-check="{g["id"]}:{d["id"]}"><span>{e(d["text"])}</span></label>' for d in g["documents"])
        main.append('<section id="preparation" class="article-section"><header class="article-section-heading"><p class="eyebrow">手元にそろえるもの</p><h2><span class="heading-phrase">まずは、</span>'
                    '<span class="heading-phrase">あるものから</span><span class="heading-phrase">確認しましょう。</span></h2></header><p>そろったものにチェックを入れると、準備の進み具合を振り返れます。同じブラウザに保存されます。</p>'
                    f'<div class="document-checklist">{docs}</div><p class="small-note">チェック項目は準備の手がかりです。提出先の案内に合わせて、追加の書類も確認しましょう。</p>'
                    f'<p class="check-progress" data-check-progress="{g["id"]}"></p></section>')
        steps = "".join(f'<li><span>{i + 1}</span><div><h3>{e(g["stepTitles"][i])}</h3><p>{e(s)}</p></div></li>' for i, s in enumerate(g["steps"]))
        details = "".join(f'<section class="article-detail"><h3>{e(s["title"])}</h3>' + "".join(f"<p>{e(t)}</p>" for t in s["paragraphs"]) + citations(s["source"], ctx.tsite) + "</section>"
                          for s in g.get("sections", []))
        main.append('<section id="steps" class="article-section"><header class="article-section-heading"><p class="eyebrow">進め方</p><h2>ひとつずつ、<span class="heading-phrase">進めて</span>'
                    f'<span class="heading-phrase">いきましょう。</span></h2></header><ol class="article-steps">{steps}</ol>{details}</section>')
    for n, s in enumerate(p["sections"]):
        main.append(section_block(n, s, ctx.table_html, len(p["sections"])))
    kids = [c for c in ctx.content if c.get("parent") == path and not p.get("hide_children")]
    if kids:
        main.append('<section class="article-section"><header class="article-section-heading"><h2>' + e(p.get("children_h2") or "この先のページ") + '</h2></header><ul class="links child-links">'
                    + "".join(f'<li><a href="{e(c["path"])}">{e(c["h1"] if len(c["h1"]) < 40 else c["title"])}</a></li>' for c in kids) + "</ul></section>")
    off = ctx.official.get(path)
    if off:
        main.append('<section id="official" class="article-section"><header class="article-section-heading"><p class="eyebrow">提出前の確認に</p><h2>最新の案内も<span class="heading-phrase">確かめましょう。</span></h2></header>'
                    f'<ul class="official-list">{off}</ul>'
                    + (f'<p class="small-note">このガイドは{e(g["factCheck"]["checkedAt"])}に公式情報と照合しました。条件・必要書類・受付方法は個別の状況や自治体等により変わります。提出前にリンク先の最新の案内も確認してください。</p>' if g else
                       f'<p class="small-note">{e(p.get("data_basis") or "")}。条件や日付は変わることがあるので、提出前にリンク先の最新の案内も確認してください。</p>')
                    + '<a href="/method/"><span class="heading-phrase">情報の確かめ方・</span><span class="heading-phrase">期限の数え方 →</span></a></section>')
    if g and g.get("faq"):
        main.append(f'<section id="article-faq" class="article-section"><header class="article-section-heading"><p class="eyebrow">気になること</p><h2>よくある質問</h2></header><div class="page-faq">{faq_html(g)}</div></section>')
    side_links = "".join(f'<a href="#{a}">{e(short(t, 18))} ↓</a>' for a, t in anchors[:6])
    parent = ctx.by_path.get(p.get("parent") or "")
    back = f'<a class="secondary-button" href="{e(parent["path"])}">{e(CRUMB.get(parent["path"], parent["title"]))}へ戻る →</a>' if parent and parent["path"] != "/" else ""
    sidebar = ('<aside class="article-sidebar"><div class="sidebar-note"><p class="eyebrow">いま確認したいところへ</p><h2>準備の道しるべ</h2>' + side_links + back + '</div>'
               '<div class="sidebar-calendar"><span aria-hidden="true">▦</span><h2>先の準備も、<br>見渡しておくと安心。</h2><p>今月から3か月の準備を、カレンダーで確認できます。</p><a href="/#calendar">カレンダーを見る →</a></div></aside>')
    # --- related
    rel = [r for r in p.get("related", []) if r["path"] in ctx.by_path][:3]
    cards = ""
    for r in rel:
        q = ctx.by_path[r["path"]]
        ic, col = art_of(q)
        cards += (f'<article class="guide-card"><div class="guide-card-art {col}">{illustration(ic)}</div><div class="guide-card-copy"><p class="eyebrow">{e(eyebrow_of(q, None))}</p>'
                  f'<h3><a href="{e(q["path"])}">{e(r["text"])}</a></h3><p>{e(q["description"])}</p><a class="card-more" href="{e(q["path"])}">確認する <span aria-hidden="true">↗</span></a></div></article>')
    related = (f'<section class="wrap page-section"><h2><span class="heading-phrase">あわせて</span><span class="heading-phrase">確認したい手続き</span></h2><div class="guide-card-grid">{cards}</div>'
               if cards else '<section class="wrap page-section">')
    related += ('<aside class="calendar-callout"><span class="calendar-mini" aria-hidden="true">▦</span><div><h2>これからの準備を、<span class="heading-phrase">カレンダーでも。</span></h2>'
                '<p>今月から3か月分を見渡して、気になる予定を確認できます。</p></div><a class="secondary-button" href="/#calendar">3か月のカレンダーを見る →</a></aside></section>')
    html_main = (crumbs(crumb_items(p, ctx.by_path)) + f'<article class="guide-article">{hero}<div class="wrap article-layout"><div class="article-main">{"".join(main)}</div>{sidebar}</div></article>' + related)
    return html_main, (faq_ld(g) if g and g.get("faq") else "")


# ---------------------------------------------------------------- the home page
def home_main(p: dict, ctx) -> str:
    lead = p.get("_answer_marked") or p.get("answer") or ""
    tpl = (ROOT / "home.html").read_text(encoding="utf-8")
    events = "".join(
        f'<a class="event-guide" href="{u}"><span class="event-icon">{illustration(ic)}</span><div><h3>{e(n)}</h3><p>{e(s)}</p></div>'
        '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg></a>' for _, n, ic, _c, u, s in HOME_EVENTS)
    near = "".join(section_block(n, s, ctx.table_html, 0) for n, s in enumerate(p["sections"]))
    return (tpl.replace("{{H1}}", phrases(p["h1"])).replace("{{LEAD}}", e(lead)).replace("{{EVENTS}}", events)
            .replace("{{SECTIONS}}", near).replace("{{CHECKED}}", e(ctx.tsite["checkedDate"])).replace("{{FAQ_LD}}", ""))


# ---------------------------------------------------------------- the pages that need the browser's saved list
def intro(kicker: str, title: str, description: str, icon: str, color: str) -> str:
    return (f'<section class="page-intro {color}"><div class="wrap intro-grid"><div><p class="eyebrow">{kicker}</p><h1>{title}</h1><p class="intro-description">{description}</p></div>'
            f'<div class="intro-illustration">{illustration(icon)}</div></div></section>')


SEARCH_FORM = ('<form class="page-search" action="/search/" role="search"><label class="visually-hidden" for="page-query">手続き名や気になること</label>'
               '<input id="page-query" name="q" type="search" placeholder="引っ越し、必要書類、年末調整など"><button class="primary-button" type="submit">探す <span aria-hidden="true">→</span></button></form>')


def search_main(index: dict) -> str:
    rows = "".join(f'<article class="search-row" data-key="{e(k)}"><div>{illustration(art_for_url(v["url"])[0])}</div><div><p class="eyebrow">{e(art_for_url(v["url"])[2])}</p>'
                   f'<h3><a href="{e(v["url"])}">{e(v["title"])}</a></h3><p>{e(v["summary"])}</p></div></article>' for k, v in index.items())
    sugg = "".join(f'<a href="/search/?q={q}">{t}</a>' for q, t in (("%E5%BC%95%E3%81%A3%E8%B6%8A%E3%81%97", "引っ越し"), ("%E5%B9%B4%E6%9C%AB%E8%AA%BF%E6%95%B4", "年末調整"), ("%E9%80%80%E8%81%B7", "退職"), ("%E5%8C%BB%E7%99%82%E8%B2%BB", "医療費")))
    return (crumbs([("手続きを検索", None)]) + intro("気になる言葉から探せます", "どんな準備を<br>確認したいですか？", "手続きの名前や、暮らしの出来事を入力してください。", "tax", "sky")
            + f'<section class="wrap page-section narrow-section">{SEARCH_FORM}<div class="search-suggestions">よく探される言葉：{sugg}</div><h2 id="search-heading">ページ一覧</h2>'
            f'<p id="search-count" role="status" aria-live="polite"></p><div id="search-results">{rows}</div><div id="search-empty" class="empty-paper" hidden><h3>近い手続きが<span class="heading-phrase">見つかりませんでした。</span></h3>'
            '<p>「引っ越し」「退職」など、少し短い言葉でも試してみてください。</p><a href="/life/">出来事から探す →</a></div></section>')


def art_for_url(url: str) -> tuple[str, str, str]:
    a = ART.get(url)
    if a:
        return a[0], a[1], a[2]
    return MONTH_ART[0], MONTH_ART[1], MONTH_ART[2]


def saved_main() -> str:
    return (crumbs([("あとで見る", None)]) + intro("ご自分のペースで読み返す", "気になる手続きを、<br>ここにまとめて。", "記事の「あとで読む」や、カレンダーの「あとで見る」で保存した内容が並びます。", "tax", "lilac")
            + '<section class="wrap page-section narrow-section"><p class="small-note">保存内容はこのブラウザに記録されます。別の端末との共有はありません。</p><div id="saved-page-list"></div>'
              '<noscript><p>保存した内容の表示にはJavaScriptを使用します。</p></noscript><div id="saved-empty" class="empty-paper"><div>' + illustration("tax")
            + '</div><h2>気になる手続きが<span class="heading-phrase">見つかったら。</span></h2><p>「あとで読む」を押すと、ここに保存できます。時間のあるときに、ゆっくり読み返してください。</p>'
              '<a class="primary-button" href="/life/">出来事から探す →</a></div></section>')


def plain_page_main(old_main_inner: str, path: str, title: str) -> str:
    """about / privacy / contact / 404: the sentences of sokuhou/sitekit.py in the frame of the new design"""
    m = re.match(r"\s*<h1>(.*?)</h1>(.*)", old_main_inner, re.S)
    h1, rest = (m.group(1), m.group(2)) if m else (title, old_main_inner)
    ic = {"/about/": ("care", "peach"), "/privacy/": ("tax", "sky"), "/contact/": ("tax", "peach"), "/404.html": ("moving", "cream")}.get(path, ("calendar", "cream"))
    return (intro("暮らしの準備と手続き", h1, "", ic[0], ic[1]).replace('<p class="intro-description"></p>', "")
            + f'<div class="wrap page-section prose-width prose-legal">{rest}</div>')
