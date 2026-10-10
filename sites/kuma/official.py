"""/official/ -- every prefecture's official bear-sighting page in one place, with what this site shows for it and the ministry's figure.

The links come from sites/kuma/links.json (the pages themselves are the publishers' own); everything else on the page is counted from the data the
build was given, so the page cannot disagree with the prefecture pages.  Nothing is copied from the linked pages: the table is this site's own
overview (which prefecture has official pages, whether this site shows records or counts for it, what the ministry's table says).
"""
from __future__ import annotations

from sites.kuma.fmt import fy_label, n, table
from sokuhou import prefectures as pf
from sokuhou.sitekit import crumbs, esc


def _links_cell(items: list[dict]) -> str:
    return "<br>".join(f'<a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["label"])}</a>' for x in items)


def _ours_cell(slug: str, lv: dict | None) -> str:
    if not lv:
        return "-"
    if slug in lv["by_pref"]:
        k = sum(len(v) for v in lv["by_pref"][slug].values())
        return f'<a href="/live/{slug}/">記録を一覧・地図で({n(k)}件)</a>'
    for c in lv["counts"]:
        if c["slug"] == slug:
            return f'<a href="/live/{slug}/">件数を月別・市町村別で({n(c["total"])}件)</a>'
    return "-"


def coverage(d: dict, links: dict, lv: dict | None) -> dict:
    """The numbers the lead sentence uses, counted from the table's own rows."""
    rows = d["rows"]
    with_links = [r for r in rows if links.get(r["short"])]
    shown = [r for r in rows if lv and (r["slug"] in lv["by_pref"] or any(c["slug"] == r["slug"] for c in lv["counts"]))]
    return {"prefectures": len(rows), "with_links": len(with_links), "shown": len(shown), "links": sum(len(links.get(r["short"]) or []) for r in rows)}


def official_page(page, d: dict, lv: dict | None, links: dict) -> str:
    cur, done = d["cur"], d["done"]
    cov = coverage(d, links, lv)
    blocks = ""
    for region_slug, region_name, shorts in pf.REGIONS:
        rows = [d["by_slug"][pf.SLUG[s]] for s in shorts if pf.SLUG[s] in d["by_slug"]]
        if not rows:
            continue
        trs = []
        for r in rows:
            items = links.get(r["short"]) or []
            cell = _links_cell(items) if items else ("(掲載しているリンクはありません)" + ("" if r["has"] else "。環境省の出没件数の表に、数値がありません"))
            env = n(r["total"][done]) if r["has"] and r["total"].get(done) is not None else "-"
            trs.append([f'<a href="/{r["slug"]}/">{esc(r["name"])}</a>', cell, _ours_cell(r["slug"], lv), env])
        blocks += f'<h2 id="{region_slug}">{esc(region_name)}</h2>\n' + table(["都道府県", "公式の出没情報(リンク)", "このサイトで見られる最新の情報", f"環境省の出没件数({fy_label(done)})"], trs) + "\n"
    names = esc("・".join(d["unlisted"]))
    unlisted_note = (f"""<h2 id="unlisted">環境省の表にない地域</h2>
<p>{names}は、環境省の出没件数・人身被害の表に載っていないため、このサイトに、都道府県のページを置いていません(「載っていない」は、「出没がない」という意味ではありません)。</p>
""" if d.get("unlisted") else "")
    cite_note = 'このサイトが取得している元データと、数え方は、<a href="/cite/">データの出典・数え方・引用のしかた</a>に書いています。' if lv else ""     # /cite/ exists only with live data
    body = f"""{crumbs([("全国", "/"), ("都道府県の公式の出没情報", None)])}
<h1>都道府県の公式のクマ出没情報(リンク集)</h1>
<p class="lead">クマの出没は、いまこのときの情報が、都道府県・市町村の公式のページに、最初に出ます。{n(cov['with_links'])}都道府県の公式のページへのリンク({n(cov['links'])}件)を、地方ごとに並べました。このサイトが、記録または件数を載せている都道府県({n(cov['shown'])}か所)には、そのページへの入り口と、環境省の速報値(出没件数)も、並べています。</p>
<p>リンク先は、各都道府県・省庁のページです。当サイトは、リンク先の内容を、写していません。県によって、地図・一覧・お知らせメールなど、出し方が違います。ページが移動・削除されていたら、<a href="/contact/">お問い合わせ</a>で、お知らせください。</p>
{blocks}{unlisted_note}<p class="notice">環境省の出没件数は、都道府県が、それぞれの方法で数えて、環境省に報告した速報値です。数え方が違うため、都道府県どうしの数の大小は、そのまま比べられません。「環境省の表に数値がありません」は、「出没がない」という意味ではありません(表に載っていない、という意味です)。{cite_note}</p>"""
    return page(path="/official/", title=f"都道府県の公式のクマ出没情報(リンク集・{n(cov['with_links'])}都道府県)",
                description=f"{n(cov['with_links'])}都道府県の、公式のクマ出没情報のページへのリンクを、地方ごとにまとめています。このサイトで見られる最新の情報と、環境省の出没件数(速報値)も、並べています。", body=body)
