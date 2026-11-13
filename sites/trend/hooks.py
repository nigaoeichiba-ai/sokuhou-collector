"""The home page, the category pages and the head of every page of trend-sokuho.com, made from the articles (sokuhou/newsite.py calls prepare() before the pages are
rendered and post() after).  A new article only needs `category`, `published` and `seq` in its content JSON: the newest one becomes "いまの話題", the cards, the category
page, the dates, the description (the first sentence of 「3行まとめ」), the breadcrumb, OGP and the structured data follow by themselves.  No text of an article is written here.

Pictures (card images, the default OGP image) are made at build time and never stored in the repository."""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import homepage  # noqa: E402
import statuspanel  # noqa: E402

HERE = Path(__file__).resolve().parent

CATS = [("kakei", "家計・値上げ", "コメや野菜の価格、給与、セールの動きなど、家計に関わる数字の記事です。省庁や公的機関の発表をもとに、店頭で使える比べ方まで紹介します。"),
        ("bousai", "防災・気象", "台風や火災予防、防災グッズの備えなど、身を守るための記事です。気象庁や消防庁、防災庁の発表をもとに、家でやることまで紹介します。"),
        ("tenki", "天気・季節", "インフルエンザや胃腸炎の流行、加湿器の手入れなど、季節と健康に関わる記事です。公的機関の報告の数字と、家庭での予防を紹介します。"),
        ("kurashi", "暮らし", "年賀はがきや電話勧誘への対応など、暮らしの手続きと困りごとの記事です。公的機関の案内をもとに、手順まで紹介します。")]
CAT_PATH = {name: f"/cat/{slug}/" for slug, name, _ in CATS}
# pages made before the `category` field existed
LEGACY = {"/trend-typhoon32/": ("防災・気象", "2026-11-07", 1), "/bousai/": ("防災・気象", "2026-11-07", 2), "/bousai-mizu-shokuryo/": ("防災・気象", "2026-11-07", 3),
          "/bousai-keitai-toilet/": ("防災・気象", "2026-11-07", 4), "/bousai-light/": ("防災・気象", "2026-11-07", 5), "/bousai-denchi-juden/": ("防災・気象", "2026-11-07", 6)}
CARD_W, CARD_H = 640, 427
OG_DEFAULT = "/assets/og-default.png"
HOME_LATEST, HOME_CATS = "<!--TOP:latest-->", "<!--TOP:cats-->"
HOME_LATEST_N = 13


ICON_ROOT_FILES = ("favicon-16.png", "favicon-32.png", "favicon-48.png", "icon-512.png")
ICON_LINES = "\n".join([
    '<link rel="icon" href="/favicon.ico" sizes="any">',
    '<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">',
    '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">',
    '<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png">',
    '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">']) + "\n"
_OLD_ICONS = "\n".join([
    '<link rel="icon" href="/favicon.ico" sizes="48x48">',
    '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">',
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">']) + "\n"


def _swap_icons(t: str) -> str:
    return t.replace(_OLD_ICONS, ICON_LINES, 1) if _OLD_ICONS in t else t


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def ja_date(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{int(y)}年{int(m)}月{int(dd)}日"


def slug_of(path: str) -> str:
    return path.strip("/")


def eyecatch_src(p: dict) -> str | None:
    for s in p.get("sections", []):
        m = re.search(r'class="eyecatch"><img src="([^"]+)"', s.get("html", "") or "")
        if m:
            return m.group(1)
    return None


def first_summary(p: dict) -> str | None:
    for s in p.get("sections", []):
        if s.get("h2") == "3行まとめ" and s.get("paras"):
            return s["paras"][0]
    return None


def first_sentences(p: dict, n: int = 2) -> str | None:
    """The first n sentences of 「3行まとめ」 (its lines read one after another), exactly as written."""
    text = three_lines(p)
    if not text:
        return None
    out = re.findall(r"[^。]+。", text)
    return "".join(out[:n]) or None


def three_lines(p: dict) -> str:
    for s in p.get("sections", []):
        if s.get("h2") == "3行まとめ":
            return "".join(s.get("paras", []))
    return ""


def card(p: dict, *, first: bool = False) -> str:
    """One card: the picture, the category, the date, the title (the only link of the card: the title's link covers the whole card), a one-line summary."""
    cat = p["category"]
    eager = 'fetchpriority="high"' if first else 'loading="lazy"'
    return (f'<article class="card{" card-hero" if first else ""}"><img src="/assets/img/card/{slug_of(p["path"])}.webp" width="{CARD_W}" height="{CARD_H}" alt="{esc(p["h1"])}" {eager}>'
            f'<div class="card-body"><p class="card-meta"><a class="card-cat" href="{CAT_PATH[cat]}">{esc(cat)}</a><time datetime="{p["published"]}">{ja_date(p["published"])}</time></p>'
            f'<h3><a href="{p["path"]}">{esc(p["h1"])}</a></h3><p class="card-sum">{esc(p["_sum"])}</p></div></article>')


def newest_first(arts: list[dict]) -> list[dict]:
    return sorted(arts, key=lambda p: (p["published"], p.get("seq", 0), p["path"]), reverse=True)


def prepare(cfg: dict, spec: dict, pages: list[dict], site_dir: Path) -> list[dict]:
    pages = json.loads(json.dumps(pages))
    by = {p["path"]: p for p in pages}
    for path, (cat, pub, seq) in LEGACY.items():
        if path in by:
            by[path].setdefault("category", cat)
            by[path].setdefault("published", pub)
            by[path].setdefault("seq", seq)
    arts = [p for p in pages if p.get("category")]
    for p in arts:
        if p["category"] not in CAT_PATH:
            raise SystemExit(f"{p['_file']}: category {p['category']!r} is not one of {list(CAT_PATH)}")
        p["published"] = p.get("published") or p["updated"]
        p["_img"] = eyecatch_src(p)
        p["_sum"] = first_summary(p) or p["answer"]
        if first_sentences(p):
            p["description"] = first_sentences(p)   # the first two sentences of 「3行まとめ」, no new sentence
        if p.get("parent") == "/":
            p["parent"] = CAT_PATH[p["category"]]
        if p.get("status_typhoon"):   # the status panel (common part): right after the lead (「3行まとめ」)
            at = next((i for i, sec in enumerate(p["sections"]) if sec.get("h2") == "3行まとめ"), -1) + 1
            p["sections"].insert(at, {"html": statuspanel.typhoon_panel(p["status_typhoon"])})
        dates = f'公開日 {ja_date(p["published"])}' + (f' / 更新日 {ja_date(p["updated"])}' if p.get("updated") else "")
        p["sections"].insert(0, {"html": f'<p class="dates">{dates}</p>'})
    ordered = newest_first(arts)
    # category pages
    for slug, name, desc in CATS:
        mine = [p for p in ordered if p["category"] == name]
        if not mine:
            continue
        rows = [[{"text": p["h1"], "href": p["path"]}, ja_date(p["published"]), ja_date(p.get("updated") or p["published"]), three_lines(p)] for p in mine]
        pages.append({"_file": f"(cat-{slug})", "path": f"/cat/{slug}/", "kind": "hub", "parent": "/", "title": f"{name}の記事一覧｜{cfg['site_name']}", "title_exact": True, "h1": f"{name}の記事一覧",
                      "crumb": name, "primary_kw": name, "intent": 2, "description": desc, "updated": max(p.get("updated") or p["published"] for p in mine), "sources": [], "hide_children": True,
                      "sections": ([{"paras": list(spec.get("category_intro", {}).get(slug, []))}] if spec.get("category_intro", {}).get(slug) else []) + [{"html": '<div class="cards">' + "".join(card(p, first=(i == 0)) for i, p in enumerate(mine)) + "</div>"},
                                   {"h2": f"{name}の記事の一覧", "table": {"caption": "", "cols": ["題", "公開日", "更新日", "3行まとめ"], "num_cols": [], "rows": rows}}],
                      "related": []})
    # the home page: the 13 newest articles, newest first (owner decision 2026-11-11).  Title and lead come from the article itself: `top_lead` (its one-line lead,
    # moved from home.json) when it has one, else the first line of its 「3行まとめ」.  A new article shows up here by itself.
    home = by["/"]
    for s in home["sections"]:
        if s.get("html") == HOME_LATEST:
            cards = []
            for a in ordered[:HOME_LATEST_N]:
                a = dict(a)
                a["_sum"] = a.get("top_lead") or a["_sum"]
                cards.append(card(a))
            s["html"] = '<div class="cards">' + "".join(cards) + "</div>"
    return pages


def _jpeg_free_card(src: Path) -> bytes:
    im = Image.open(src).convert("RGB")
    r = CARD_W / CARD_H
    w, h = im.size
    if w / h > r:
        nw = round(h * r)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w / r)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    out = io.BytesIO()
    im.resize((CARD_W, CARD_H)).save(out, "WEBP", quality=80)
    return out.getvalue()


def _og_default(site_dir: Path) -> bytes:
    im = Image.new("RGB", (1200, 630), "white")
    logo = Image.open(site_dir / "assets" / "img" / "logo.png").convert("RGBA")
    h = 300
    logo = logo.resize((round(logo.size[0] * h / logo.size[1]), h))
    im.paste(logo, ((1200 - logo.size[0]) // 2, (630 - h) // 2), logo)
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


def _add_json_image(text: str, image_url: str) -> str:
    def fix(m: re.Match) -> str:
        d = json.loads(m.group(1))
        if d.get("@type") == "Article" and "image" not in d:
            d["image"] = [image_url]
        return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + "</script>"
    return re.sub(r'<script type="application/ld\+json">(.*?)</script>', fix, text, flags=re.S)


DEEP_MIN_CHARS = 2000
# Articles published before the depth bar (2026-11-09): the character count is not required of them (owner: no padding just to reach a number), but they are
# reviewed against the other bars (own view, own text, own content, research) and thickened only with real content.  A NEW article is not on this list.
DEEP_GRANDFATHERED = {"/trend-nengajo-print/", "/trend-fire-alarm/", "/trend-influenza-44/", "/trend-vegetable-price/", "/trend-crab-phone-call/", "/bousai-light/",
                      "/bousai-mizu-shokuryo/", "/trend-wage-2026-09/", "/trend-rice-price/", "/bousai-keitai-toilet/", "/bousai-denchi-juden/", "/trend-humidifier-care/",
                      "/trend-gastroenteritis-winter/", "/trend-typhoon32/", "/trend-blackfriday-price/", "/bousai/"}


def deep_problems(pages: dict, content: list[dict]) -> list[str]:
    """The depth bar for articles (desk's rule 2026-11-09): a new article needs 2,000 readable characters and an own table or chart, or it must be declared a bridge
    page (`"noindex": true` in its JSON, which keeps it out of search).  The own view, own text and research bars cannot be measured: the writer declares them."""
    from sokuhou import seokit
    out = []
    for p in content:
        if not p.get("category") or p.get("noindex") or p["path"] in DEEP_GRANDFATHERED:
            continue
        info = seokit.read_main(pages[p["path"].strip("/") + "/index.html"])
        if info["chars"] < DEEP_MIN_CHARS:
            out.append(f"{p['path']}: {info['chars']} readable characters (a deep article needs {DEEP_MIN_CHARS}); thicken it with content of its own, or declare it a bridge page with \"noindex\": true")
        if not (info["tables"] or info["charts"]):
            out.append(f"{p['path']}: no table and no chart of its own (a deep article needs one)")
    return out


# ---- 年賀状印刷の総額シミュレーター(記事 /trend-nengajo-hayawari/ の総額表のあとに入れる)。
# オーナー確認が済むまで本番に出さない: config.json の "nengajo_sim" が true か、環境変数 TREND_NENGAJO_SIM=1 のときだけ組み込む。
NENGAJO_SIM_DIR = HERE / "nengajo_sim"
NENGAJO_SIM_PAGE = "trend-nengajo-hayawari/index.html"
NENGAJO_SIM_BEFORE = "<h2>割引率だけ見ると損するワケ</h2>"
NENGAJO_SIM_OLD_STEP = "送る枚数を先に決める。30枚前後なら、この記事の表がそのまま使えます"
NENGAJO_SIM_NEW_STEP = "送る枚数を先に決める。枚数と宛名印刷の有無を、上のシミュレーターに入れて、各社の総額を比べる"
NENGAJO_SIM_SOURCES = [("https://nenga.print-netsquare.com/info/price/", "年賀状スクエア 料金表"), ("https://happy-card.jp/ne/page/price/index.html", "おたより本舗 価格表"),
                       ("https://nenga.n-pri.jp/price/", "しまうまプリント 年賀状印刷の価格"), ("https://nenga-org.aisatsujo.jp/guide/order/price.html", "挨拶状ドットコム 価格"),
                       ("https://rakpo.com/price/", "Rakpo 価格")]


def nengajo_sim_enabled(cfg: dict) -> bool:
    env = os.environ.get("TREND_NENGAJO_SIM")      # "1" forces it on, "0" forces it off (the tests use both); otherwise config.json decides
    if env in ("0", "1"):
        return env == "1"
    return bool(cfg.get("nengajo_sim"))


def add_nengajo_sim(pages: dict) -> None:
    t = pages.get(NENGAJO_SIM_PAGE)
    if not isinstance(t, str) or NENGAJO_SIM_BEFORE not in t or NENGAJO_SIM_OLD_STEP not in t:
        raise SystemExit("nengajo sim: the insertion point or the step that points at the 30-sheet table is not in the article")
    js, css = (NENGAJO_SIM_DIR / "nengajo-sim.js").read_text(encoding="utf-8"), (NENGAJO_SIM_DIR / "nengajo-sim.css").read_text(encoding="utf-8")
    block = (NENGAJO_SIM_DIR / "nengajo-sim.html").read_text(encoding="utf-8").replace(
        "<!--SIM:links-->", "、".join(f'<a href="{u}" rel="noopener">{html.escape(n)}</a>' for u, n in NENGAJO_SIM_SOURCES))
    ver = lambda s: hashlib.sha1(s.encode()).hexdigest()[:8]
    pages["assets/nengajo-sim.js"], pages["assets/nengajo-sim.css"] = js, css
    t = t.replace(NENGAJO_SIM_BEFORE, block + NENGAJO_SIM_BEFORE, 1).replace(NENGAJO_SIM_OLD_STEP, NENGAJO_SIM_NEW_STEP, 1)
    t = t.replace('<link rel="stylesheet" href="/assets/style.css', f'<link rel="stylesheet" href="/assets/nengajo-sim.css?v={ver(css)}">\n<link rel="stylesheet" href="/assets/style.css', 1)
    t = t.replace("</body>", f'<script src="/assets/nengajo-sim.js?v={ver(js)}" defer></script>\n</body>', 1)
    pages[NENGAJO_SIM_PAGE] = t


def post(pages: dict, content: list[dict], cfg: dict, spec: dict, site_dir: Path) -> dict:
    problems = deep_problems(pages, content)
    if problems:
        raise SystemExit("depth bar not met:\n  " + "\n  ".join(problems))
    base = cfg["site_url"].rstrip("/")
    name = cfg["site_name"]
    by_rel = {("index.html" if p["path"] == "/" else p["path"].strip("/") + "/index.html"): p for p in content}
    pages["assets/og-default.png"] = _og_default(site_dir)
    for n in ICON_ROOT_FILES:  # favicons are asked for at the site root (owner decision 2026-11-10: favicon A, speech bubble x lightning)
        pages[n] = (site_dir / "assets" / n).read_bytes()
    for p in content:
        if p.get("category") and p.get("_img"):
            pages[f"assets/img/card/{slug_of(p['path'])}.webp"] = _jpeg_free_card(site_dir / p["_img"].lstrip("/"))
    for rel in [r for r in pages if r.endswith("index.html") and isinstance(pages[r], str)]:
        t, p = pages[rel], by_rel.get(rel)
        if p and p.get("category") and p.get("_img"):
            src, (w, h) = p["_img"], Image.open(site_dir / p["_img"].lstrip("/")).size
            atype = "article"
        else:
            src, (w, h), atype = OG_DEFAULT, (1200, 630), "website"
        t = t.replace('<meta property="og:type" content="website">', f'<meta property="og:type" content="{atype}">', 1)
        t = t.replace('<meta name="twitter:card" content="summary">', '<meta name="twitter:card" content="summary_large_image">', 1)
        t = re.sub(r'(<meta property="og:url" content="[^"]*">\n)', lambda m: m.group(1) + f'<meta property="og:image" content="{esc(base + src)}">\n<meta property="og:image:width" content="{w}">\n<meta property="og:image:height" content="{h}">\n'
                   f'<meta name="twitter:image" content="{esc(base + src)}">\n', t, count=1)
        if p and p.get("title_exact"):
            exact = p["title"]
            t = t.replace(f"<title>{esc(exact)} | {esc(name)}</title>", f"<title>{esc(exact)}</title>", 1)
            t = t.replace(f'<meta property="og:title" content="{esc(exact)} | {esc(name)}">', f'<meta property="og:title" content="{esc(exact)}">', 1)
        t = _swap_icons(t)
        # ヘッダー・フッター(オーナー指示 2026-11-10。ロゴ画像に名前の文字が入っているため、テキストの名前は並べない=二重表示にしない)
        t = t.replace('<a class="brand" href="/"><span class="logo" aria-hidden="true">', '<a class="brand" href="/" aria-label="今日の話題 速報×深掘り"><span class="logo">', 1)
        t = t.replace("</span>今日の話題</a>\n<nav", "</span></a>\n<nav", 1)
        t = t.replace('<header class="site">', '<div class="wrap"><p class="tagline" style="margin:.4rem 0 0;font-size:.82rem;color:#555">ニュースの見出しで終わらせない「速報×深掘り」メディア</p></div>\n<header class="site">', 1)
        t = t.replace('<p class="legal">', '<p class="src"><span>「今日の話題」は、気になる速報ニュースをどこよりも深く、多角的に読み解くメディアです。</span></p>\n<p class="legal">', 1)
        t = t.replace("<span>&copy; 今日の話題</span>", "<span>&copy; 今日の話題 速報×深掘り All Rights Reserved.</span>", 1)
        if p and p.get("category"):
            t = _add_json_image(t, base + src)
        if rel == "index.html":
            hero = (p or {}).get("hero")
            if hero:
                t = t.replace('<link rel="stylesheet"', f'<link rel="preload" as="image" href="{hero["img"]}" fetchpriority="high">\n<link rel="stylesheet"', 1)
            org = {"@context": "https://schema.org", "@type": "Organization", "name": name, "url": base + "/", "logo": base + "/assets/img/logo.png"}
            t = t.replace('<link rel="stylesheet"', '<script type="application/ld+json">' + json.dumps(org, ensure_ascii=False) + '</script>\n<link rel="stylesheet"', 1)
        if rel == "index.html":   # the top page: the approved prototype's design replaces the shared header, body, footer and stylesheet (owner instruction 2026-11-11)
            t = homepage.apply(t, p, content, spec, cfg, site_dir, slug_of, CARD_W, CARD_H, CAT_PATH, HOME_LATEST_N)
        pages[rel] = t
    if nengajo_sim_enabled(cfg):
        add_nengajo_sim(pages)
    return pages
