"""Makes sites/trend/content/*.json and the pictures from the articles written outside the repository (the reading format: article-opus.json, and the parent page's Markdown).

    python sites/trend/build_content.py

Inputs (private working folders, never the repository): the children and the typhoon article as article-opus.json, the parent page v7 as Markdown, the pictures.
Nothing from the malls is read or written here: the product cards come later from the private store, not from this file.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
DRIVE = Path("H:/マイドライブ")
KOBO = Path("C:/Dropbox/AI/Claude/副業/sokuhou-sites/work/kobo/out")
CHILD_DIR = DRIVE / "文章ツール" / "公開用の形_防災子ページ4本"
PARENT_MD = DRIVE / "文章ツール" / "防災親ページ_最新稿_v7.md"
SOKUHOU = DRIVE / "sokuhou"
TYPHOON = Path("C:/Dropbox/AI/Claude/副業/sokuhou-sites/work/kobo/out/trend-typhoon32/article-opus.json")
IMG_SRC = KOBO / "trend-images"
UPDATED = "2026-11-07"

PARENT = "/bousai/"
CHILDREN = {
    "bousai-mizu-shokuryo": ("/bousai-mizu-shokuryo/", "水と食料の備蓄", "水と食料の保管と期限管理のコツ"),
    "bousai-keitai-toilet": ("/bousai-keitai-toilet/", "携帯トイレの使い方", "携帯トイレの使い方と使用後の処理"),
    "bousai-light": ("/bousai-light/", "防災用ライトの選び方", "防災用ライトの選び方と置き場所"),
    "bousai-denchi-juden": ("/bousai-denchi-juden/", "防災用モバイルバッテリーの容量", "モバイルバッテリーの容量と電池の備蓄"),
}
PARENT_TITLE = "防災グッズのチェックリスト、8項目で家の備えを確認しよう"
TYPHOON_PATH = "/trend-typhoon32/"
# a title in a sentence becomes a link when it is the title of a page of this site
LINKS = {f"「{PARENT_TITLE}」": PARENT, "「防災用モバイルバッテリーの容量の目安と、電池の備蓄」": "/bousai-denchi-juden/"}

# illustration marks -> (picture file in assets/img, alt text); a mark without a picture is dropped (reported by the build)
EYE = {
    "bousai-mizu-shokuryo": ("eye-mizu.jpg", "黄色の背景に、赤と黒の大きな文字で「水と食料の備蓄」「1人1日3リットル」と書かれたポスター風の絵。下にペットボトルの水、缶詰、レトルト食品の袋"),
    "bousai-keitai-toilet": ("eye-toilet.jpg", "「携帯トイレの使い方」「使ったあとの処理まで」の文字と、右側に携帯トイレの箱と黒いごみ袋を描いた絵"),
    "bousai-light": ("eye-light.jpg", "赤と黄色の背景に「防災ライトの選び方」「明るさ・点灯時間・電池」の文字と、懐中電灯とランタンを描いた絵"),
    "bousai-denchi-juden": ("eye-denchi.jpg", "「防災モバイルバッテリー」「容量の目安」「乾電池の備蓄」の文字と、モバイルバッテリー、スマホ、乾電池を描いた絵"),
}
PICS = {
    "bousai-keitai-toilet": [("携帯トイレの使い方、4コマ", "toilet-4koma.webp", "携帯トイレの使い方を4コマで示した絵。便器にポリ袋をかぶせる、携帯トイレを設置して凝固剤を入れる、座って使う、袋の口を結ぶ"),
                              ("便器にごみ袋を2枚重ねて", "toilet-section.webp", "便器にごみ袋を2枚重ねてかぶせ、内側の袋に細かくちぎった新聞紙を入れた断面図")],
    "bousai-denchi-juden": [("容量ごとの充電回数の目安", "denchi-capacity.jpg", "10,000mAhのモバイルバッテリーでスマホ約2回、20,000mAhで約4回。実際に使える量は表示の65〜70%ほどと示した絵")],
    "bousai-light": [("家の見取り図", "light-map.jpg", "家の見取り図に、寝室の枕元、トイレ、玄関、非常用バッグの4か所のライトの置き場所を描いた絵")],
    "bousai-mizu-shokuryo": [("家の中に水の箱を分けて置いた", "water-map.jpg", "家の中に水の箱を分けて置いた断面図。キッチン、押し入れ、寝室のクローゼットに1箱ずつ"),
                              ("「1日目」「2日目」と書いた箱", "food-week.jpg", "1日目から7日目と書いた箱が7つ並び、1つの箱の中にその日の食料が入っている絵")],
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def linkify(text: str) -> str | None:
    out, hit = esc(text), False
    for k, href in LINKS.items():
        if esc(k) in out:
            out = out.replace(esc(k), f'<a href="{href}">{esc(k)}</a>')
            hit = True
    return f"<p>{out}</p>" if hit else None


def figure(src: str, alt: str) -> dict:
    return {"html": f'<figure class="pic"><img src="/assets/img/{src}" alt="{esc(alt)}" width="1200" loading="lazy"></figure>'}


def picture_files() -> None:
    d = HERE / "assets" / "img"
    d.mkdir(parents=True, exist_ok=True)
    jobs = [(SOKUHOU / "アイキャッチ_台風32号_v3.webp", "typhoon-32.jpg", 1280),
            (SOKUHOU / "ヘッダー画像_防災特集_v3.webp", "bousai-header.jpg", 1600),
            (SOKUHOU / "イラスト試作_使い方4コマ.webp", "toilet-4koma.webp", 1200),
            (SOKUHOU / "イラスト試作_断面図.webp", "toilet-section.webp", 1200)]
    for n, out in (("light_map", "light-map.jpg"), ("water_map", "water-map.jpg"), ("food_week", "food-week.jpg"), ("denchi_capacity_v2", "denchi-capacity.jpg"),
                   ("eyecatch_water", "eye-mizu.jpg"), ("eyecatch_toilet", "eye-toilet.jpg"), ("eyecatch_light", "eye-light.jpg"), ("eyecatch_denchi", "eye-denchi.jpg")):
        p = IMG_SRC / f"{n}.png"
        if p.exists():
            jobs.append((p, out, 1280 if n.startswith("eyecatch") else 1200))
    for src, name, w in jobs:
        im = Image.open(src).convert("RGB")
        im = im.resize((w, round(im.size[1] * w / im.size[0])))
        im.save(d / name, quality=82)
    logo = Image.open(SOKUHOU / "ロゴ決定_A案_透過.png").convert("RGBA")
    logo = logo.resize((round(logo.size[0] * 160 / logo.size[1]), 160))
    logo.save(d / "logo.png", optimize=True)


def sentence_answer(a: dict) -> str:
    first = a["lead"].split("。")[0] + "。"
    return first if 40 <= len(first) <= 80 else a["tldr"][0]


EXTRA = {
    "bousai-mizu-shokuryo": {"after_h2": "水は、分散して保管する", "description": "水と食料の備蓄を、家のどこにどう分けて置くか、賞味期限をどう切らさずに続けるかを紹介します。水は1人1日3リットルが目安で、人数別の量も、表でそのまま確かめられます。",
        "table": {"caption": "水の備蓄の目安(1人1日3リットル)", "cols": ["人数", "3日分(L)", "7日分(L)"], "num_cols": [0, 1, 2], "rows": [[f"{n}人", str(9 * n), str(21 * n)] for n in range(1, 6)]}},
    "bousai-keitai-toilet": {"after_h2": "携帯トイレの使い方", "description": "携帯トイレの使い方と、使ったあとの保管・処理のしかたを、手順で紹介します。携帯トイレがないときにごみ袋で代用する方法と、備える回数の目安も、表で確かめられます。",
        "answer": "携帯トイレは、買っておくだけでは使えません。使い方と、使ったあとの保管・処理を知っておけば、慌てずにすみます。",
        "table": {"caption": "携帯トイレの備蓄の目安(7日分、1人1日5〜6回)", "cols": ["人数", "1日5回の場合(回)", "1日6回の場合(回)"], "num_cols": [0, 1, 2], "rows": [[f"{n}人", str(35 * n), str(42 * n)] for n in range(1, 6)]}},
    "bousai-light": {"after_h2": "防災用の懐中電灯は、明るさ・点灯時間・電池で選ぶ", "description": "防災用の懐中電灯を、明るさ(ルーメン)・点灯時間・電池で選ぶ目安と、寝室の枕元・トイレ・玄関・非常用バッグなど、家の中での置き場所を、場面ごとに紹介します。",
        "table": {"caption": "明るさ(ルーメン)の目安", "cols": ["使う場面", "明るさの目安(ルーメン)"], "num_cols": [1], "rows": [["足元や手元の作業", "50〜100"], ["数メートル先まで見たい", "150〜200"], ["遠くまで照らしたい", "300以上"]]}},
    "bousai-denchi-juden": {"after_h2": "モバイルバッテリーの容量は、家族のスマホの台数で選ぶ", "table": {"caption": "モバイルバッテリーでスマホを充電できる回数の目安", "cols": ["容量", "スマホの充電回数の目安"], "num_cols": [], "rows": [["10,000mAh", "約2回"], ["20,000mAh", "約4回"]]}, "description": "防災用のモバイルバッテリーは、家族のスマホの台数と何日使うかで容量を決めます。容量の目安、充電の優先順位、乾電池の備蓄と期限の読み方を、順に紹介します。"},
}


def child_page(key: str) -> dict:
    a = json.loads((CHILD_DIR / key / "article-opus.json").read_text(encoding="utf-8"))
    path, kw, crumb = CHILDREN[key]
    pics = list(PICS.get(key, []))
    secs: list[dict] = [{"h2": "3行まとめ", "paras": list(a["tldr"])}]
    ef = EYE.get(key)
    if ef and (HERE / "assets" / "img" / ef[0]).exists():
        secs.insert(0, {"html": f'<p class="eyecatch"><img src="/assets/img/{ef[0]}" width="1280" alt="{esc(ef[1])}" fetchpriority="high"></p>'})
    for s in a["sections"]:
        cur: dict = {"h2": s["heading"], "paras": []}
        for p in s["paras"]:
            if p.startswith("[アフィリ候補"):
                continue
            if p.startswith("[イラスト"):
                hit = next((x for x in pics if x[0] in p), None)
                if hit and (HERE / "assets" / "img" / hit[1]).exists():
                    secs.append(cur)
                    secs.append(figure(hit[1], hit[2]))
                    cur = {"paras": []}
                continue
            lk = linkify(p)
            if lk:
                secs.append(cur)
                secs.append({"html": lk})
                cur = {"paras": []}
            else:
                cur["paras"].append(p)
        if s.get("bullets"):
            secs.append(cur)
            secs.append({"html": "<ul>" + "".join(f"<li>{esc(b)}</li>" for b in s["bullets"]) + "</ul>"})
            cur = {"paras": []}
        secs.append(cur)
    secs = [x for x in secs if x.get("html") or x.get("paras") or x.get("table") or x.get("chart") or x.get("h2")]
    extra = EXTRA.get(key, {})
    if extra.get("table"):
        for x in secs:
            if x.get("h2") and x["h2"] == extra["after_h2"]:
                x["table"] = extra["table"]
                break
        else:
            raise SystemExit(f"{key}: the section {extra['after_h2']!r} was not found")
    return {"updated": UPDATED, "data_basis": "2026年11月7日現在", "sources": [], "path": path, "kind": "article", "parent": PARENT,
            "title": a["title"], "h1": a["title"], "crumb": crumb, "primary_kw": kw, "intent": 4, "description": extra.get("description", a["description"]), "answer": extra.get("answer", sentence_answer(a)),
            "sections": secs, "related": [{"path": PARENT, "text": PARENT_TITLE}]}


def table_rows() -> dict:
    rows = []
    for n in range(1, 6):
        rows.append([f"{n}人", f"{9 * n}", f"{21 * n}", f"{35 * n}", f"{42 * n}", f"{9 * n}", f"{21 * n}"])
    return {"caption": "家族の人数ごとの、水・携帯トイレ・食事の備蓄の目安", "cols": ["人数", "水 3日分(L)", "水 7日分(L)", "携帯トイレ 7日分 1日5回(回)", "携帯トイレ 7日分 1日6回(回)", "食事 3日分(食)", "食事 7日分(食)"],
            "num_cols": [0, 1, 2, 3, 4, 5, 6], "rows": rows}


CHECK = ["水", "食料", "携帯トイレ", "ライト", "電池と充電器", "ラジオ", "雨具と防水仕様の靴", "救急用品"]


def checklist_html() -> str:
    items = "".join(f'<li><label><input type="checkbox" class="chk"> {esc(c)}</label></li>' for c in CHECK)
    return ('<div class="checklist"><ul>' + items + '</ul><p class="tally" aria-live="polite">そろっている防災グッズ: <b id="chk-n">0</b> / 8項目</p></div>'
            '<script>(function(){var b=document.querySelectorAll(".chk"),n=document.getElementById("chk-n");'
            'function u(){var c=0;b.forEach(function(x){if(x.checked)c++});n.textContent=c}b.forEach(function(x){x.addEventListener("change",u)})})();</script>')


def parent_page() -> dict:
    text = PARENT_MD.read_text(encoding="utf-8")
    lines = [l for l in text.split("\n") if not l.startswith("<!--")]
    secs: list[dict] = []
    lead, cur, mode = "", None, "lead"
    tldr: list[str] = []
    drop = ("防災庁の呼びかけの全体は、", "台風が近づいているときは、「台風の前に、家でやることは6つ」")
    for l in lines:
        s = l.strip()
        if not s or s.startswith("# "):
            continue
        if s.startswith("## "):
            h = s[3:]
            if h == "3行まとめ":
                mode = "tldr"
                continue
            mode = "sec"
            cur = {"h2": h, "paras": []}
            secs.append(cur)
            continue
        if mode == "lead":
            lead += s
            continue
        if mode == "tldr":
            if s.startswith("- "):
                tldr.append(s[2:])
                continue
            mode = "sec"
        if s.startswith("[表:"):
            secs.append({"table": table_rows()})
            cur = {"paras": []}
            secs.append(cur)
            continue
        if s == "[チェックリスト]":
            secs.append({"html": checklist_html()})
            cur = {"paras": []}
            secs.append(cur)
            continue
        if s == "[子ページの案内]":
            lis = "".join(f'<li><a href="{p}">{esc(t)}</a></li>' for p, t in (
                ("/bousai-mizu-shokuryo/", "水と食料の備蓄を続ける、保管と期限管理のコツ"), ("/bousai-keitai-toilet/", "携帯トイレの使い方と、使用後の保管・処理のしかた"),
                ("/bousai-light/", "防災用ライトの選び方、明るさ・電池・置き場所"), ("/bousai-denchi-juden/", "防災用モバイルバッテリーの容量の目安と、電池の備蓄")))
            secs.append({"html": f'<ul class="links">{lis}</ul>'})
            cur = {"paras": []}
            secs.append(cur)
            continue
        if s.startswith("> "):
            body = s[2:]
            if body.startswith("ライフハック:"):
                secs.append({"html": f'<aside class="hack"><strong>{esc(body.split(":")[0])}</strong>{esc(body.split(":", 1)[1])}</aside>'})
            else:
                secs.append({"html": f'<aside class="hack">{esc(body)}</aside>'})
            cur = {"paras": []}
            secs.append(cur)
            continue
        # sentences that point at pages this site does not have are dropped
        for d in drop:
            if d in s:
                s = ""
        if not s:
            continue
        cur["paras"].append(s)
        more = None
        if s.startswith("食料は、") and "缶詰" in s:
            more = ("/bousai-mizu-shokuryo/", "水と食料の保管と期限管理のコツを読む")
        elif s.startswith("携帯トイレは、"):
            more = ("/bousai-keitai-toilet/", "携帯トイレの使い方と、使用後の保管・処理を読む")
        elif s.startswith("ライトは、"):
            more = ("/bousai-light/", "防災用ライトの選び方と置き場所を読む")
        elif s.startswith("電池と充電器は、"):
            more = ("/bousai-denchi-juden/", "モバイルバッテリーの容量と電池の備蓄を読む")
        if more:
            secs.append({"html": f'<p class="more"><a href="{more[0]}">{esc(more[1])}</a></p>'})
            cur = {"paras": []}
            secs.append(cur)
    head = {"html": '<p class="eyecatch"><img src="/assets/img/bousai-header.jpg" width="1600" alt="今日の話題 防災特集。携帯トイレ、凝固剤、防臭袋の絵と、携帯トイレの使い方などの見出し" fetchpriority="high"></p>'}
    secs = [x for x in secs if x.get("html") or x.get("paras") or x.get("table") or x.get("h2")]
    intro = {"paras": [lead]}
    secs = [head, intro, {"h2": "3行まとめ", "paras": tldr}] + secs
    return {"updated": UPDATED, "data_basis": "2026年11月7日現在", "sources": ["bousaicho"], "path": PARENT, "kind": "article", "parent": "/",
            "title": PARENT_TITLE, "h1": PARENT_TITLE, "crumb": "防災グッズのチェックリスト", "primary_kw": "防災グッズのチェックリスト", "intent": 4,
            "description": "防災庁の呼びかけをもとに、水・食料・携帯トイレ・ライトなど防災グッズ8項目のチェックリストと、人数別の備蓄量の早見表で、家の備えを確かめます。足りないものは、まず3日分から。",
            "answer": "防災庁は11月2日、家庭で水と食料を最低3日分、できれば1週間分備蓄するよう呼びかけました。",
            "sections": secs, "related": []}


def typhoon_page() -> dict:
    a = json.loads(TYPHOON.read_text(encoding="utf-8"))
    secs: list[dict] = [{"html": '<p class="eyecatch"><img src="/assets/img/typhoon-32.jpg" width="1280" alt="' + esc(a["eyecatch"]["alt"]) + '" fetchpriority="high"></p>'},
                        {"h2": "3行まとめ", "paras": list(a["tldr"])}]
    for s in a["sections"]:
        paras = [p for p in s["paras"] if not p.startswith("[アフィリ候補") and not p.startswith("[イラスト")]
        out: dict = {"h2": s["heading"], "paras": []}
        rest = []
        for p in paras:
            lk = linkify(p)
            if lk:
                rest.append(lk)
            else:
                out["paras"].append(p)
        years = [b for b in s.get("bullets", []) if re.match(r"^\d{4}年", b)]
        if years:
            rows = []
            for b in years:
                ys, n = b.rsplit(" ", 1)
                rows += [[y, n.replace("個", "")] for y in re.findall(r"\d{4}", ys)]
            rows.sort(key=lambda r: (-int(r[1]), int(r[0])))
            out["table"] = {"caption": "年間の台風の発生数が32個以上の年(気象庁)", "cols": ["年", "発生数(個)"], "num_cols": [0, 1], "rows": rows}
            intro = [p for p in out["paras"] if "次のとおりです" in p]
            out["paras"] = [p for p in out["paras"] if "次のとおりです" not in p] + [p.replace("次のとおりです", "次の表のとおりです") for p in intro]
        if s["heading"].startswith("台風32号の進路予報"):
            out["chart"] = {"kind": "line", "unit": "m/s", "title": "台風32号の最大風速の予報(7日18時の実況と、8日18時・9〜11日15時の予報)", "labels": ["7日", "8日", "9日", "10日", "11日"], "values": [18, 25, 35, 40, 35],
                            "desc": "気象庁の発表。中心付近の最大風速は、7日18時の実況が18m/s、予報が8日18時25m/s、9日15時35m/s、10日15時40m/s、11日15時35m/sで、10日に最も強くなる予報"}
        if s["heading"].startswith("32号の発生は32年ぶり"):
            out["chart"] = {"kind": "bar", "unit": "個", "title": "年間の台風の発生数(気象庁)", "labels": ["1964年", "1965年", "1966年", "1967年", "1971年", "1974年", "1989年", "1994年", "2026年(32号まで)"],
                            "values": [34, 32, 35, 39, 36, 32, 32, 36, 32],
                            "desc": "年間の発生数が32個以上の年と、今年(32号まで)。1967年の39個が最多で、1971年と1994年が36個、1966年が35個、1964年が34個、1965年・1974年・1989年が32個"}
        secs.append(out)
        for r in rest:
            secs.append({"html": r})
    return {"updated": a["updated"], "data_basis": "2026年11月7日18時45分現在", "sources": ["jma"], "path": TYPHOON_PATH, "kind": "article", "parent": "/",
            "title": a["title"], "h1": a["title"], "crumb": "台風32号の進路予報", "primary_kw": a["seo_keyword"], "intent": 1, "description": a["description"], "answer": a["answer"],
            "sections": secs, "related": [{"path": PARENT, "text": PARENT_TITLE}]}


def home_page() -> dict:
    t = typhoon_page()
    card = ('<article class="lead-card"><a href="' + TYPHOON_PATH + '"><img src="/assets/img/typhoon-32.jpg" width="1280" alt="' + esc(t["sections"][0]["html"].split('alt="')[1].split('"')[0]) + '">'
            '<span class="lead-title">' + esc(t["title"]) + '</span></a><p>' + esc(t["answer"]) + '</p></article>')
    rows = [["水", "1人1日3リットル。最低3日分、できれば1週間分", "水と食料の備蓄を続ける、保管と期限管理のコツ"],
            ["食料", "水と同じ日数分。缶詰、レトルト、ごはん、麺類が基本", "水と食料の備蓄を続ける、保管と期限管理のコツ"],
            ["携帯トイレ", "1日5〜6回×人数×日数分", "携帯トイレの使い方と、使用後の保管・処理のしかた"],
            ["ライト", "ランタン型とヘッドライトを、使う場面で使い分ける", "防災用ライトの選び方、明るさ・電池・置き場所"],
            ["電池と充電器", "スマホの充電を守る。電池は同じ種類をそろえる", "防災用モバイルバッテリーの容量の目安と、電池の備蓄"],
            ["ラジオ", "スマホの電池を使わずに情報を得る", "—"],
            ["雨具と防水仕様の靴", "両手があくレインコートと、水を通さない靴", "—"],
            ["救急用品", "けがの手当て用品と、薬・お薬手帳", "—"]]
    return {"updated": UPDATED, "data_basis": "2026年11月7日現在", "sources": ["bousaicho"], "path": "/", "kind": "hub", "title": "今日の話題 速報×深掘り 今の話題を速く深く知る",
            "h1": "今日の話題 速報×深掘り", "primary_kw": "今日の話題 速報", "intent": 1,
            "description": "今日の話題を、ニュースの見出しだけで終わらせず、気象庁や防災庁など公的な発表の数字で確かめて、速く深く伝えるサイトです。最新は台風32号の進路予報と、防災グッズ8項目のチェックリストです。",
            "answer": "今日の話題を、気象庁や防災庁など公的な発表の数字で確かめて紹介します。最新は台風32号(11月7日)です。",
            "sections": [{"h2": "最新の記事", "html": card},
                         {"h2": "防災特集: 家の備えを8項目で確かめる", "paras": ["防災庁は11月2日、家庭で水と食料を最低3日分、できれば1週間分備蓄するよう呼びかけました。当サイトは、防災グッズを8項目にまとめ、親ページのチェックリストと、項目ごとの詳しいページで、家の備えを確かめられるようにしています。",
                                                                  "まず親ページ「" + PARENT_TITLE + "」で、足りないものを確かめます。そのあと、足りない項目のページで、量や選び方を読みます。親ページのチェックリストは、印をつけると、そろっている項目の数が分かります。印は、お使いの画面の中だけで数えていて、サイトには送りません。"],
                          "table": {"caption": "防災グッズ8項目と、読めるページ", "cols": ["項目", "目安", "詳しいページ"], "num_cols": [], "rows": rows}},
                         {"html": '<p class="more"><a href="' + PARENT + '">' + esc(PARENT_TITLE) + '</a></p><ul class="links"><li><a href="/bousai-mizu-shokuryo/">水と食料の備蓄を続ける、保管と期限管理のコツ</a></li><li><a href="/bousai-keitai-toilet/">携帯トイレの使い方と、使用後の保管・処理のしかた</a></li><li><a href="/bousai-light/">防災用ライトの選び方、明るさ・電池・置き場所</a></li><li><a href="/bousai-denchi-juden/">防災用モバイルバッテリーの容量の目安と、電池の備蓄</a></li></ul>'},
                         {"h2": "このサイトについて", "paras": ["今日の話題を、ニュースの見出しだけで終わらせず、公的な発表の数字で確かめて紹介するサイトです。結論を先に書き、数字は出典のあるものだけを載せます。事件・事故・訃報・医療・政治などの重い話題は扱いません。","記事は、速報と深掘りを1セットにします。速報では、いま何が起きているかを、発表の数字で伝えます。深掘りでは、ほかの年や地域と比べたり、家でできる備えに落としたりして、読んだあとに何をすればよいかが分かるようにします。数字や予報は、時間とともに変わります。各ページに、数字を確かめた日時を書いています。"]}]}


def main() -> None:
    picture_files()
    pages = {"home": home_page(), "bousai": parent_page(), "trend-typhoon32": typhoon_page()}
    for k in CHILDREN:
        pages[k] = child_page(k)
    d = HERE / "content"
    for p in d.glob("*.json"):
        p.unlink()
    for name, page in pages.items():
        (d / f"{name}.json").write_text(json.dumps(page, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", ", ".join(pages))


if __name__ == "__main__":
    sys.exit(main())
