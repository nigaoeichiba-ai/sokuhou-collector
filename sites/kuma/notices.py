"""/notices/ -- the bear notices that municipalities and prefectures announce on their own sites (read from their RSS / Atom feeds every morning).

Only the title, the date and the publisher are shown, and every title links to the publisher's own page.  Notices about tenders, proposals and the
like are left out.  The feeds are collected by sokuhou/feedscan.py (data/muni_feeds.json); a municipality without a feed does not appear here.
"""
from __future__ import annotations

import re

from sites.kuma.fmt import jp_date, md, n
from sokuhou import feedscan
from sokuhou.sitekit import crumbs, esc

NOISE = re.compile(r"入札|プロポーザル|業務委託|契約|公告|公募|見積|受託|落札")


def bear_notices(feeds: dict | None) -> list[dict]:
    """The bear items of the feeds that were read, newest first, once per address (the same page can be in two feeds)."""
    out, seen = [], set()
    for f in (feeds or {}).get("feeds", []):
        if not f.get("ok"):
            continue
        for i in f["items"]:
            key = i["link"].split("#", 1)[0]
            if key in seen or not i.get("date") or not feedscan.is_bear(i) or NOISE.search(i["title"]):
                continue
            seen.add(key)
            out.append({"publisher": f["name"], "title": i["title"], "link": i["link"], "date": i["date"]})
    out.sort(key=lambda x: (x["date"], x["publisher"]), reverse=True)
    return out


def feed_counts(feeds: dict | None) -> tuple[int, int]:
    """(feeds read, publishers) -- what the lead sentence says it checked."""
    ok = [f for f in (feeds or {}).get("feeds", []) if f.get("ok")]
    return len(ok), len({f["name"] for f in ok})


def notices_page(page, items: list[dict], feeds: dict | None) -> str:
    n_feeds, n_pub = feed_counts(feeds)
    rows = "".join(f'<li><a href="{esc(x["link"])}" rel="noopener" target="_blank">{esc(x["title"])}</a><span>{md(x["date"])}・{esc(x["publisher"])}</span></li>' for x in items)
    newest = items[0]["date"]
    body = f"""{crumbs([("全国", "/"), ("自治体のクマ関連のお知らせ", None)])}
<h1>自治体のクマ関連のお知らせ(新着)</h1>
<p class="lead">都道府県・市町村が、自分のサイトで発表した、クマに関するお知らせを、新しい順に並べています。{n(n_pub)}の自治体の、{n(n_feeds)}のお知らせの配信(RSS)を、毎朝確認して、直近3週間の分から、クマの話題を拾っています。いまは{n(len(items))}件で、最新は{jp_date(newest)}です。</p>
<ul class="link-list news-list">{rows}</ul>
<p class="notice">題名は、各自治体のページの表記のままです。リンク先は、各自治体の公式サイトです。当サイトは、リンク先の内容を写していません。お知らせの配信(RSS)を出していない自治体は、ここに出ません(出ていない=お知らせがない、ではありません)。クマの目撃の記録は、<a href="/live/">最新の目撃情報</a>に、環境省のお知らせは、<a href="/news/">環境省のお知らせ</a>にあります。入札や委託などのお知らせは、載せていません。</p>"""
    return page(path="/notices/", title=f"自治体のクマ関連のお知らせ(新着・{n(len(items))}件)",
                description=f"都道府県・市町村が自分のサイトで発表した、クマに関するお知らせを、新しい順に並べています(直近3週間・{n(len(items))}件)。リンク先は各自治体の公式サイトです。", body=body)
