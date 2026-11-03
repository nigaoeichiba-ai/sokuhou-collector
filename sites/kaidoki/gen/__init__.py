"""Writes sites/kaidoki/content/*.json and site.json from the sales in facts.py and the pages in pages_*.py, for today's date (JST).

    python -m sites.kaidoki.gen           (from sokuhou-collector/)  write
    python -m sites.kaidoki.gen --stale   read only: what has passed since the facts were read, and what is still unannounced
KAIDOKI_TODAY=2026-11-03 fixes the day (tests).
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import CHECKED, TODAY, d, ev_span

SITE = Path(__file__).resolve().parents[1]


def all_pages() -> list[dict]:
    from . import pages_amazon, pages_calc, pages_kaden, pages_misc, pages_rakuten, pages_trust
    out = []
    for m in (pages_misc, pages_calc, pages_trust, pages_rakuten, pages_amazon, pages_kaden):
        out += m.pages()
    from .extra import extra
    from .extra2 import extra2
    ex = extra()
    from .extra3 import extra3
    for part in (extra2(), extra3()):
        for k, v in part.items():
            ex.setdefault(k, []).extend(v)
    for p in out:
        p["updated"] = TODAY.isoformat()
        add = ex.get(p["path"], [])
        if add:
            secs = p["sections"]
            p["sections"] = secs[:-1] + add + secs[-1:] if secs[-1]["h2"].startswith("最終確認") else secs + add
    return out


def write() -> int:
    pages = all_pages()
    content = SITE / "content"
    content.mkdir(exist_ok=True)
    for f in content.glob("*.json"):
        f.unlink()
    for p in pages:
        slug = p["path"].strip("/").replace("/", "-") or "home"
        (content / f"{slug}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    site = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
    site["updated"] = TODAY.isoformat()
    site.update({
        "nav": [["日程カレンダー", "/calendar/", "/calendar/"], ["楽天", "/rakuten/", "/rakuten/"], ["Amazon", "/amazon/sale-calendar/", "/amazon/"],
                ["買い時", "/buytime/", "/buytime/"], ["計算ツール", "/calc/", "/calc/"]],
        "footer_html": "最終的な日程は、主催者の公式発表でご確認ください。日程は変更されることがあります。",
        "purpose": "大型セールの日程と、家電などの買い時を、主催者とメーカーの発表で確かめられた範囲だけ載せること。買う日を決める人が、日付と条件を見落とさないための道具です。",
        "update_text": "主催者が日程を発表したら、その日のうちに日付を足し、各ページの更新日を書き換えます。ページは毎日つくり直し、日付・曜日・あと何日は計算で出しています。直した内容は「訂正と更新の記録」に残します。",
        "disclaimer": [
            "日程は、主催者が変更することがあります。買う前に、必ず主催者の公式ページで最新の内容を確かめてください。",
            "このサイトは、日付と条件の事実を伝えるものです。商品の価格は扱わず、どの商品やどのモールが得かの判定もしません。",
            "ページ内のリンクからモールで買い物をすると、このサイトに紹介料が入ることがあります。",
        ],
        "method": [
            "主催者の特設ページやプレスリリースを開いて、開始と終了の日時を読み取り、表に組み直しています。曜日と「あと何日」は日付から計算しています。",
            "公式で確認できない日程は、予想で補わず、未発表と書いています。",
            "各社の表や文章は写していません。日付や条件という事実だけを、当サイトの表に組み直しています。",
        ],
        "sources_style": "credit",
        "credits": [],
        "sources": {"official": {"org": "各主催者・メーカー・業界団体", "table": "公式発表", "credit": "各主催者・メーカー・業界団体の公式発表をもとに作成",
                                 "url": "", "basis": CHECKED, "fetched": CHECKED}},
    })
    (SITE / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(pages)


def stale() -> list[str]:
    """Read only.  Sales whose end passed after CHECKED (the sentences were written when they were still ahead), and the sales still unannounced."""
    from .facts import EVENTS, UNANNOUNCED
    out = []
    for e in sorted(EVENTS, key=lambda e: e["start"]):
        if d(CHECKED) < d(e["end"]) < TODAY:
            out.append(f"過ぎた: {e['name']} {ev_span(e)}")
    out += [f"未発表のまま(公式を再確認): {n} ({m}) {why}" for n, m, why in UNANNOUNCED]
    return out
