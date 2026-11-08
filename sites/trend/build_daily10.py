"""Pours the 10 articles of 2026-11-08 (the desk's final text, 本日分10案_本文_2026-11-08.md) into sites/trend/content/*.json, word for word.

    python sites/trend/build_daily10.py

The text between 「ここから本文」 and 「ここまで本文」 is the article; the 実装メモ is not.  Nothing is reworded: a line is a paragraph, a "|" table becomes a table, the last line (出典:) becomes the page's credit.
Pictures: assets/img/eye-<slug>.webp (the eyecatch, made by Codex) and ill-<slug>.webp (one illustration, placed after the section named in FIG_AFTER).
The home page's list of the 10 (grouped by the desk's categories) is added to content/home.json.  No mall data is read or written here.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
BODY = Path("H:/マイドライブ/sokuhou/inbox/本日分10案_本文_2026-11-08.md")
IMG_SRC = Path("C:/Dropbox/AI/Claude/副業/sokuhou-sites/work/kobo/out/trend-images-20261108")
UPDATED = "2026-11-08"
BASIS = "2026年11月8日現在"

CRUMB = {"trend-rice-price": "コメの価格", "trend-fire-alarm": "火災警報器の点検", "trend-vegetable-price": "野菜の相場", "trend-wage-2026-09": "9月の給与",
         "trend-influenza-44": "インフルエンザの定点報告", "trend-blackfriday-price": "ブラックフライデー前の価格記録", "trend-crab-phone-call": "海産物の電話勧誘",
         "trend-nengajo-print": "年賀はがきの印刷", "trend-humidifier-care": "加湿器の手入れ", "trend-gastroenteritis-winter": "感染性胃腸炎の対策"}
# the main term of a page must stand in its title and h1 (the desk's text is not reworded), so it is a phrase of the title; the desk's search words are kept as the second term
KW = {"trend-rice-price": "5kg平均2,816円", "trend-fire-alarm": "火災警報器", "trend-vegetable-price": "たまねぎは平年の55％", "trend-wage-2026-09": "実質2.2％増", "trend-influenza-44": "インフルエンザは定点10.26人",
      "trend-blackfriday-price": "ブラックフライデー", "trend-crab-phone-call": "カニの電話勧誘", "trend-nengajo-print": "年賀はがき", "trend-humidifier-care": "加湿器の手入れ",
      "trend-gastroenteritis-winter": "感染性胃腸炎"}
# the section after which the illustration stands (prefix of the h2)
FIG_AFTER = {"trend-rice-price": "買うときは、単価と", "trend-fire-alarm": "点検は、この順番で", "trend-vegetable-price": "店頭での使い方",
             "trend-wage-2026-09": "理由の1つ目", "trend-influenza-44": "基本の予防", "trend-blackfriday-price": "記録に残すのは4つ", "trend-crab-phone-call": "場面別の対応",
             "trend-nengajo-print": "自宅の印刷とネット注文", "trend-humidifier-care": "毎日の手入れは", "trend-gastroenteritis-winter": "場面別の対策"}
# related pages (the text of the link is the title of the other page)
RELATED = {"trend-rice-price": ["trend-vegetable-price", "trend-wage-2026-09"], "trend-fire-alarm": ["/bousai/"], "trend-vegetable-price": ["trend-rice-price", "trend-wage-2026-09"],
           "trend-wage-2026-09": ["trend-rice-price", "trend-vegetable-price"], "trend-influenza-44": ["trend-gastroenteritis-winter", "trend-humidifier-care"],
           "trend-blackfriday-price": ["trend-nengajo-print", "trend-rice-price"], "trend-crab-phone-call": ["trend-nengajo-print"],
           "trend-nengajo-print": ["trend-blackfriday-price", "trend-crab-phone-call"], "trend-humidifier-care": ["trend-influenza-44", "trend-gastroenteritis-winter"],
           "trend-gastroenteritis-winter": ["trend-influenza-44", "trend-humidifier-care"]}
# product shelves (definitions are in shelves.json; the cards stay hidden until the private store has products): slug -> [(h2 prefix, shelf id)]
SHELF_AFTER = {"trend-humidifier-care": [("毎日の手入れは", "humidifier"), ("湿度の物差し", "hygrometer")], "trend-nengajo-print": [("自宅の印刷とネット注文", "nengajo-paper")]}
CATEGORY_ORDER = ["家計・値上げ", "防災・気象", "天気・季節", "暮らし"]
ALT = json.loads((Path(__file__).resolve().parent / "daily10_alt.json").read_text(encoding="utf-8")) if (Path(__file__).resolve().parent / "daily10_alt.json").exists() else {}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def split_articles(text: str) -> list[dict]:
    out = []
    for blk in re.split(r"\n---\n", text):
        m = re.search(r"実装メモ：スラッグ案 (\S+)／カテゴリ (\S+)／検索の言葉「(.+?)」", blk)
        if not m:
            continue
        a, b = blk.index("ここから本文") + len("ここから本文"), blk.index("ここまで本文")
        out.append({"slug": m.group(1), "category": m.group(2), "kw": m.group(3), "lines": blk[a:b].strip("\n").split("\n"), "memo": blk[blk.index("実装メモ"):blk.index("ここから本文")]})
    return out


def parse(lines: list[str]) -> dict:
    title, lead, secs, credit = "", [], [], ""
    cur = None
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if not s:
            continue
        if s.startswith("# "):
            title = s[2:]
        elif s.startswith("## "):
            cur = {"h2": s[3:], "paras": []}
            secs.append(cur)
        elif s.startswith("出典: "):
            credit = s[len("出典: "):]
        elif s.startswith("|"):
            rows = [s]
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|[-\s|]+\|$", r)]
            cur["table"] = {"caption": cur["h2"], "cols": cells[0], "num_cols": [], "rows": cells[1:]}
        elif cur is None:
            lead.append(s)
        else:
            cur["paras"].append(s)
    return {"title": title, "lead": "".join(lead), "secs": secs, "credit": credit}


def answer_of(lead: str, tldr: str) -> str:
    sents = [x + "。" for x in lead.split("。") if x]
    for n in (1, 2):
        a = "".join(sents[:n])
        if 40 <= len(a) <= 80:
            return a
    return tldr if 40 <= len(tldr) <= 80 else sents[0]


def images() -> None:
    d = HERE / "assets" / "img"
    for p in sorted(x for x in list(IMG_SRC.glob("eye-*.png")) + list(IMG_SRC.glob("ill-*.png")) if not re.search(r"-v\d[a-z]$", x.stem)):   # the chosen file only (the variants stay in the work folder)
        w = 1280 if p.name.startswith("eye-") else 1200
        im = Image.open(p).convert("RGB")
        im = im.resize((w, round(im.size[1] * w / im.size[0])))
        im.save(d / (p.stem + ".webp"), quality=82)


def article(a: dict, titles: dict[str, str], labels: dict[str, str]) -> dict:
    slug = a["slug"]
    p = parse(a["lines"])
    d = HERE / "assets" / "img"
    secs: list[dict] = []
    eye, ill = d / f"eye-{slug}.webp", d / f"ill-{slug}.webp"
    if eye.exists():
        secs.append({"html": f'<p class="eyecatch"><img src="/assets/img/eye-{slug}.webp" width="1280" alt="{esc(ALT[slug]["eye"])}" fetchpriority="high"></p>'})
    tldr = next(s for s in p["secs"] if s["h2"] == "3行まとめ")["paras"]
    ans = answer_of(p["lead"], tldr[0])
    rest = p["lead"][len(ans):] if p["lead"].startswith(ans) else p["lead"]
    if rest:
        secs.append({"paras": [rest]})
    for s in p["secs"]:
        secs.append(s)
        if ill.exists() and s["h2"].startswith(FIG_AFTER[slug]):
            secs.append({"html": f'<figure class="pic"><img src="/assets/img/ill-{slug}.webp" alt="{esc(ALT[slug]["ill"])}" width="1200" loading="lazy"></figure>'})
        for w, sid in SHELF_AFTER.get(slug, []):
            if s["h2"].startswith(w):
                secs.append({"html": f'<div class="shelf" data-shelf="{sid}" data-label="{esc(labels[sid])}" hidden></div><script src="/assets/shelf.js" defer></script>'})
    related = []
    for r in RELATED[slug]:
        if r.startswith("/"):
            related.append({"path": r, "text": "防災グッズのチェックリスト、8項目で家の備えを確認しよう"})
        else:
            related.append({"path": f"/{r}/", "text": titles[r]})
    return {"updated": UPDATED, "data_basis": BASIS, "sources": [], "credit": p["credit"], "path": f"/{slug}/", "kind": "article", "parent": "/", "title": p["title"], "h1": p["title"],
            "crumb": CRUMB[slug], "primary_kw": KW[slug], "secondary_kw": [a["kw"]], "intent": 4 if slug in ("trend-blackfriday-price", "trend-nengajo-print", "trend-humidifier-care") else 1,
            "description": p["lead"], "answer": ans, "sections": secs, "related": related}


def main() -> int:
    arts = split_articles(BODY.read_text(encoding="utf-8"))
    if len(arts) != 10:
        raise SystemExit(f"expected 10 articles, found {len(arts)}")
    sys.path.insert(0, str(HERE.parents[1]))
    from sokuhou import mallstore  # noqa: E402
    labels = {s["id"]: s["label"] for s in mallstore.load_shelves(HERE)}
    images()
    titles = {a["slug"]: parse(a["lines"])["title"] for a in arts}
    cdir = HERE / "content"
    for a in arts:
        (cdir / f"{a['slug']}.json").write_text(json.dumps(article(a, titles, labels), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # the home page: the 10 articles by category
    home = json.loads((cdir / "home.json").read_text(encoding="utf-8"))
    home["sections"] = [s for s in home["sections"] if s.get("h2") != "本日の新着記事(カテゴリ別)"]
    blocks = []
    for cat in CATEGORY_ORDER:
        mine = [a for a in arts if a["category"] == cat]
        if mine:
            blocks.append(f"<h3>{esc(cat)}</h3><ul class=\"links\">" + "".join(f'<li><a href="/{a["slug"]}/">{esc(titles[a["slug"]])}</a></li>' for a in mine) + "</ul>")
    new = {"h2": "本日の新着記事(カテゴリ別)", "html": "".join(blocks)}
    idx = next(i for i, s in enumerate(home["sections"]) if s.get("h2") == "最新の記事") + 1
    home["sections"].insert(idx, new)
    home["updated"], home["data_basis"] = UPDATED, BASIS
    (cdir / "home.json").write_text(json.dumps(home, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", len(arts), "articles and the home list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
