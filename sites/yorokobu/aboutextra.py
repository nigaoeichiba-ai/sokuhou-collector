"""What the operator page (/about/) says besides the legal minimum: how the site is made, how a correction is announced, and the history of changes (content/changelog.json).

sokuhou/sitekit.py makes /about/ for every site; this block is put in before its 免責事項 heading (the `finish` hook of legal_pages), so the shared file stays as it is.
The company's name is not here: it is on the operator line of /about/ and nowhere else (owner, 2026-10-19).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sokuhou.sitekit import esc

HERE = Path(__file__).resolve().parent
FILE = HERE / "content" / "changelog.json"
MARK = "<h2>免責事項</h2>"
KINDS = ("更新", "訂正")


def entries(path: Path | None = None) -> list[dict]:
    f = path or FILE
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("entries", [])


def problems(es: list[dict]) -> list[str]:
    """What is wrong with the list: a date that is not a date, an unknown kind, an empty text, not newest first."""
    out = []
    last = None
    for e in es:
        try:
            d = date.fromisoformat(e["date"])
        except (KeyError, ValueError):
            out.append(f"bad date: {e.get('date')!r}")
            continue
        if e.get("kind") not in KINDS:
            out.append(f"{e['date']}: kind must be one of {KINDS}")
        if not (e.get("text") or "").strip():
            out.append(f"{e['date']}: empty text")
        if last and d > last:
            out.append(f"{e['date']}: not newest first")
        last = d
    return out


def block(es: list[dict] | None = None) -> str:
    es = entries() if es is None else es
    rows = "".join(f'<li><time datetime="{esc(e["date"])}">{esc(e["date"].replace("-", "年", 1).replace("-", "月", 1))}日</time>'
                   f'{"<b class=\'fix\'>訂正</b>" if e["kind"] == "訂正" else ""}{esc(e["text"])}</li>' for e in es)
    return ('<h2>編集方針と作り方</h2>'
            '<p>載せる商品の選び方、文章の書き方、数字の扱いは<a href="/policy/">編集方針</a>にまとめています。このサイトの作り方は次のとおりです。</p>'
            '<ul><li><b>商品の情報</b>は、楽天ウェブサービスなどが示す情報を毎日取得し直して載せています。価格と在庫は、取得した日時をページに示します。</li>'
            '<li><b>文章</b>は、決まりに沿って書き、点検しています。店の説明文や他のサイトの文章を写すことはしません。</li>'
            '<li><b>数字の集計</b>(データ室など)は、取得したデータから計算します。調査会社などの数字は、出典を示しています。</li>'
            '<li><b>公開の前</b>に、リンク切れ、表示の崩れ、数字と文章の食い違いを調べ、通ったものだけを公開しています。</li></ul>'
            '<h2>訂正のお知らせ</h2>'
            '<p>誤りに気づいたときは、すぐに直し、下の更新の履歴に「訂正」として日付と内容を残します。お気づきの点は<a href="/contact/">お問い合わせ</a>からお知らせください。</p>'
            f'<h2 id="history">更新の履歴</h2><ul class="changelog">{rows}</ul>\n')


def inject(html: str) -> str:
    """The /about/ page gets the block before its 免責事項 heading; every other page is returned as it is."""
    if "<h1>運営者情報</h1>" not in html or MARK not in html:
        return html
    return html.replace(MARK, block() + MARK, 1)
