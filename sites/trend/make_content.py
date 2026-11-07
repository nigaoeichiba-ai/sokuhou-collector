"""One-off helper: turns an article of the reading format (article-opus.json, written outside the repository) into sites/trend/content/<slug>.json.

    python sites/trend/make_content.py <article-opus.json> <slug>

The article text is the site's own writing (no mall data).  Product slots are not copied: the cards come later, from the private store.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def convert(a: dict, slug: str) -> dict:
    secs = [{"h2": "3行まとめ", "paras": list(a["tldr"])}]
    eye = a.get("eyecatch")
    if eye:
        secs.insert(0, {"html": f'<p class="eyecatch"><img src="/assets/img/{slug}.jpg" width="1280" height="853" alt="{eye["alt"]}" style="max-width:100%;height:auto"></p>'})
    for s in a["sections"]:
        paras = [p for p in s["paras"] if not p.startswith("[アフィリ候補") and not p.startswith("[イラスト")]
        out = {"h2": s["heading"], "paras": paras}
        years = [b for b in s.get("bullets", []) if re.match(r"^\d{4}年", b)]
        if years:
            rows = []
            for b in years:
                ys, n = b.rsplit(" ", 1)
                for y in re.findall(r"\d{4}", ys):
                    rows.append([y, n.replace("個", "")])
            rows.sort(key=lambda r: (-int(r[1]), int(r[0])))
            out["table"] = {"caption": "年間の台風の発生数が32個以上の年(気象庁)", "cols": ["年", "発生数(個)"], "num_cols": [0, 1], "rows": rows}
            # the list sits in the table now: put it after the paragraph that introduces it
            intro = [p for p in out["paras"] if "次のとおりです" in p]
            rest = [p for p in out["paras"] if "次のとおりです" not in p]
            out["paras"] = rest + [p.replace("次のとおりです", "次の表のとおりです") for p in intro]
        elif s.get("bullets"):
            out["paras"] += s["bullets"]
        if s["heading"].startswith("台風32号の進路予報"):
            out["chart"] = {"kind": "line", "unit": "m/s", "title": "台風32号の最大風速の予報(各日15時)", "labels": ["7日", "8日", "9日", "10日", "11日"],
                            "values": [18, 25, 35, 40, 35],
                            "desc": "気象庁の11月7日15時45分発表。中心付近の最大風速は、7日15時の実況が18m/s、予報が8日15時25m/s、9日15時35m/s、10日15時40m/s、11日15時35m/sで、10日に最も強くなる予報"}
        if s["heading"].startswith("32号の発生は32年ぶり"):
            out["chart"] = {"kind": "bar", "unit": "個", "title": "年間の台風の発生数(気象庁)", "labels": ["1964年", "1965年", "1966年", "1967年", "1971年", "1974年", "1989年", "1994年", "2026年(32号まで)"],
                            "values": [34, 32, 35, 39, 36, 32, 32, 36, 32],
                            "desc": "年間の発生数が32個以上の年と、今年(32号まで)。1967年の39個が最多で、1971年と1994年が36個、1966年が35個、1964年が34個、1965年・1974年・1989年が32個"}
        secs.append(out)
    return {
        "updated": a["updated"], "data_basis": "2026年11月7日15時現在", "sources": ["jma"],
        "path": f"/articles/{slug}/", "kind": "article", "parent": "/",
        "title": a["title"], "h1": a["title"], "primary_kw": a["seo_keyword"], "intent": 1,
        "description": a["description"], "answer": a["answer"],
        "sections": secs,
        "related": [],
    }


if __name__ == "__main__":
    a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    slug = sys.argv[2]
    page = convert(a, slug)
    (HERE / "content" / f"{slug}.json").write_text(json.dumps(page, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", slug, len(json.dumps(page, ensure_ascii=False)))
