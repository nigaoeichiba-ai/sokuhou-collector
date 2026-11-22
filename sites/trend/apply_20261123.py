#!/usr/bin/env python3
"""2026-11-23: (1) the credit line of 25 articles -> the final drafts' source section (kind + date only);
(2) the JAF battery title/h1/answer back to the final draft; (3) add the Meiji price-revision article.
Safe to run twice."""
import glob
import json
import os
import re
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")
DRIVE = "H:/マイドライブ/AI/Notion/今日の話題/"

FINALS = {
    "trend-aeon-blackfriday-2026": "記事最終稿_イオンBF_2026-11-20.md",
    "trend-amazon-blackfriday-nittei": "記事最終稿_AmazonBF日程_2026-11-20.md",
    "trend-chusho-chinage": "記事最終稿_中小賃上げ_2026-11-18.md",
    "trend-google-store-blackfriday": "記事最終稿_GoogleストアBF_2026-11-20.md",
    "trend-heat-shock-kan": "記事最終稿_ヒートショック_2026-11-18.md",
    "trend-houni-kyaku-saita-10gatsu": "記事最終稿_訪日客最多_2026-11-20.md",
    "trend-ibonoito-nesage-2027": "記事最終稿_揖保乃糸値上げ_2026-11-18.md",
    "trend-kandansa-hirou": "記事最終稿_寒暖差疲労_2026-11-18.md",
    "trend-kfc-haitoku-burger": "記事最終稿_KFCバーガー_2026-11-18.md",
    "trend-kouyou-miagoro-2026": "記事最終稿_紅葉見頃_2026-11-20.md",
    "trend-lawson-morisugi": "記事最終稿_ローソン盛りすぎ_2026-11-18.md",
    "trend-mercian-nesage-2027": "記事最終稿_メルシャン値上げ_2026-11-18.md",
    "trend-mikan-hatsuseri-saikou": "記事最終稿_みかん初セリ_2026-11-18.md",
    "trend-nenmatsu-chosei-kaisei-fuyo62": "記事最終稿_年末調整改正_2026-11-20.md",
    "trend-nozomi-zensekishitei": "記事最終稿_のぞみ全席指定_2026-11-20.md",
    "trend-raize-kairyo-nesage": "記事最終稿_ライズ改良_2026-11-18.md",
    "trend-starbucks-capsule-toy": "記事最終稿_スタバカプセル_2026-11-18.md",
    "trend-tiger-glicia-grill": "記事最終稿_タイガーグリル_2026-11-18.md",
    "trend-winter-tire-kanki": "記事最終稿_冬タイヤと寒気_2026-11-18.md",
    "trend-xiaomi-18pro-hatsubai": "記事最終稿_XiaomiBF_2026-11-19.md",
    "trend-elnino-danto-2026": "記事最終稿_エルニーニョ暖冬_2026-11-21.md",
    "trend-norovirus-ryuukouki": "記事最終稿_ノロウイルス_2026-11-21.md",
    "trend-jaf-battery-nenmatsu": "記事最終稿_JAFバッテリー_2026-11-21.md",
    "trend-seijoishii-shinshohin-matsuri": "記事最終稿_成城石井新商品_2026-11-21.md",
}
# the influenza article's final is not in the Drive folder under a dated name: the desk's instruction lists the lines
CREDIT_LINES = {
    "trend-influenza-46-hokkaido-keiho": ["公的機関の発表資料（2026年11月20日）", "公的機関の発表資料（2026年11月13日）",
                                          "地方自治体の発表に基づく報道（2026年11月19日）", "地方自治体の発表に基づく報道（2026年11月20日）"],
}
OLD = "各社の発表と報道をもとに作成"


def source_lines(path):
    t = open(path, encoding="utf-8").read()
    m = re.search(r"##\s*出典\s*\n(.*?)(?:\n---|\n##|\Z)", t, re.S)
    assert m, path
    lines = [x[2:].strip() for x in m.group(1).strip().splitlines() if x.startswith("- ")]
    assert lines, path
    return lines


def load(slug):
    p = os.path.join(CONTENT, slug + ".json")
    return p, open(p, encoding="utf-8").read()


def set_credit(slug, lines):
    p, raw = load(slug)
    new = "、".join(lines)
    out, n = re.subn(r'"credit":\s*"(?:[^"\\]|\\.)*"', lambda m: '"credit": ' + json.dumps(new, ensure_ascii=False), raw, count=1)
    assert n == 1, slug
    json.loads(out)
    if out != raw:
        open(p, "w", encoding="utf-8", newline="").write(out)
        return True
    return False


def fix_credits():
    n = 0
    for slug, f in FINALS.items():
        n += set_credit(slug, source_lines(DRIVE + f))
    for slug, lines in CREDIT_LINES.items():
        n += set_credit(slug, lines)
    return n


JAF_OLD = "年末年始の出動、4割超はバッテリー上がり。帰省前の点検が先"
JAF_NEW = "年末年始の車の帰省はバッテリー点検から！出発前に確認したい備え"


def fix_jaf():
    n = 0
    for p in glob.glob(os.path.join(CONTENT, "*.json")):
        raw = open(p, encoding="utf-8").read()
        out = raw.replace(JAF_OLD, JAF_NEW)
        if p.endswith("trend-jaf-battery-nenmatsu.json"):
            d = json.loads(out)
            d["answer"] = "年末年始の帰省前に、バッテリーの点検と連絡先の確認を済ませる"
            out = json.dumps(d, ensure_ascii=False, indent=1) + "\n"
        if out != raw:
            json.loads(out)
            open(p, "w", encoding="utf-8", newline="").write(out)
            n += 1
    return n


def rakuten(q):
    return ("https://hb.afl.rakuten.co.jp/hgc/583f273a.77c989b6.583f273b.0a6a5fff/?pc="
            + urllib.parse.quote("https://search.rakuten.co.jp/search/mall/" + urllib.parse.quote(q) + "/", safe=""))


def amazon(q):
    return "https://www.amazon.co.jp/s?k=" + urllib.parse.quote(q) + "&amp;tag=amazonmacs-22"


def a(href, text):
    return f'<a href="{href}" rel="nofollow sponsored noopener" target="_blank">{text}</a>'


def inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def md_sections(md, links):
    body = md.split("\n## 出典")[0]
    lines = body.splitlines()[1:]
    secs, para, i = [], [], 0

    def flush():
        if para:
            secs.append({"paras": [inline(x) for x in para]})
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            flush()
        elif ln.startswith("## "):
            flush()
            secs.append({"h2": ln[3:].strip()})
        elif ln.startswith("### "):
            flush()
            secs.append({"html": f"<h3>{inline(ln[4:].strip())}</h3>"})
        elif ln.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(inline(lines[i][2:].strip()))
                i += 1
            i -= 1
            secs.append({"html": "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"})
        elif re.match(r"\d+\. ", ln):
            flush()
            items = []
            while i < len(lines) and (re.match(r"\d+\. ", lines[i]) or lines[i].startswith("   ")):
                if re.match(r"\d+\. ", lines[i]):
                    items.append([re.sub(r"^\d+\. ", "", lines[i]).strip()])
                else:
                    items[-1].append(lines[i].strip())
                i += 1
            i -= 1
            secs.append({"html": "<ol>" + "".join("<li>" + "<br>".join(inline(x) for x in it) + "</li>" for it in items) + "</ol>"})
        elif ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            cols, rows = rows[0], rows[2:]
            secs.append({"table": {"caption": "", "cols": cols, "num_cols": [], "rows": rows}})
        elif ln.startswith("【リンク設置"):
            flush()
            secs.append({"html": links})
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return secs


def add_meiji():
    slug = "trend-meiji-nesage-2027"
    p = os.path.join(CONTENT, slug + ".json")
    md = open(DRIVE + "記事最終稿_明治値上げ65品_2026-11-23.md", encoding="utf-8").read()
    title = re.match(r"# (.+)", md).group(1).strip()
    secs = md_sections(md, "<p>" + a(rakuten("チーズ"), "楽天市場でチーズを探す") + "（PR）</p><p>"
                       + a(amazon("バター"), "Amazonでバターを探す") + "（PR）</p>")
    lead = secs[0]["paras"][0]
    secs.insert(0, {"html": '<p class="eyecatch"><img src="/assets/img/eye-trend-meiji-nesage-2027.webp" width="1280" alt="'
                    + title + '" fetchpriority="high"></p>'})
    related = [{"path": "/trend-ibonoito-nesage-2027/", "text": None}, {"path": "/trend-mercian-nesage-2027/", "text": None},
               {"path": "/trend-nissui-nesage/", "text": None}]
    for r in related:
        d = json.load(open(os.path.join(CONTENT, r["path"].strip("/") + ".json"), encoding="utf-8"))
        r["text"] = d["h1"]
    page = {
        "updated": "2026-11-23", "data_basis": "2026年11月23日現在", "sources": [],
        "credit": "企業の発表資料（2026年11月20日）",
        "path": f"/{slug}/", "top_lead": "明治が2026年11月20日、チーズ・バター・アイスクリーム・レトルトカレーの計65品の価格改定を発表しました。",
        "kind": "article", "parent": "/", "title": title, "h1": title, "category": "家計", "published": "2026-11-23", "seq": 130,
        "crumb": "明治の値上げ", "primary_kw": "明治", "secondary_kw": ["明治 値上げ 2027 チーズ アイス"], "intent": 1,
        "description": "明治が2027年1月1日出荷分からチーズ・バター・アイスなど65品を値上げ。レトルトカレーは2月1日出荷分から。品群ごとの開始日と改定率の目安、年内の買い置きの考え方をまとめます。",
        "answer": "値上げは1月1日出荷分から。年内は使い切れる量だけ買い足せば十分",
        "related": related, "sections": secs,
    }
    cat = json.load(open(os.path.join(CONTENT, "trend-ibonoito-nesage-2027.json"), encoding="utf-8"))["category"]
    page["category"] = cat
    page["seq"] = max(json.load(open(f, encoding="utf-8")).get("seq", 0) for f in glob.glob(os.path.join(CONTENT, "trend-*.json"))) + 1
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(page, ensure_ascii=False, indent=1) + "\n")
    # reverse links (the related lists are two-way)
    for r in related:
        rp = os.path.join(CONTENT, r["path"].strip("/") + ".json")
        d = json.load(open(rp, encoding="utf-8"))
        if not any(x["path"] == page["path"] for x in d["related"]):
            raw = open(rp, encoding="utf-8").read()
            d["related"].append({"path": page["path"], "text": title})
            open(rp, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    print("credits changed:", fix_credits())
    print("jaf files changed:", fix_jaf())
    add_meiji()
    print("meiji added")
