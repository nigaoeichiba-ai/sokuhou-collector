"""Permitted bear captures (Ministry of the Environment, provisional): the ranking page and the block on each prefecture page.

Everything is read from data/env_capture_kuma.json.  The figures are captures permitted for damage prevention and for population
control under a prefecture's plan; they are NOT sightings and they are counted in heads, so they are never mixed into the sighting tables.
"""
from __future__ import annotations

from sites.kuma import charts
from sites.kuma.fmt import jp_date, n, ratio_text, table
from sokuhou import prefectures as pf
from sokuhou.sitekit import crumbs, esc

NOTE = ("許可捕獲(被害防止目的での捕獲と、特定計画による数の調整)の捕獲数を、都道府県などから聞き取った環境省の<strong>速報値</strong>で、後から変更されることがあります。"
        "「捕殺」は、捕獲して殺処理した頭数、「非捕殺」は、放獣などをした頭数です。出没件数とは別の統計で、頭数で数えています。")
NOT_LISTED = "環境省の表は、近年クマの目撃・捕獲の実績がない県(香川・愛媛・高知と、福岡から沖縄までの8県)を載せていません。"


def fy_label(y: str) -> str:
    """'H20' -> '平成20年度', 'R07' -> '令和7年度' (this table starts in Heisei 20)."""
    return f"{'平成' if y[0] == 'H' else '令和'}{int(y[1:])}年度"


def short_label(y: str) -> str:
    """'H20' -> 'H20', 'R07' -> 'R7' (for chart axes)."""
    return f"{y[0]}{int(y[1:])}"


def prepare(raw: dict | None) -> dict | None:
    if not raw:
        return None
    years = raw["years"]
    cur, done = years[-1], years[-2]
    by = {p["name"]: p["by_year"] for p in raw["prefectures"]}
    ranked = sorted(by, key=lambda p: (-by[p][done][0], p))
    rank, last = {}, None
    for i, p in enumerate(ranked):
        if by[p][done][0] != last:
            last, pos = by[p][done][0], i + 1
        rank[p] = pos
    return {"raw": raw, "years": years, "cur": cur, "done": done, "by": by, "ranked": ranked, "rank": rank,
            "national": raw["national"], "species": raw["species"], "updated": raw["updated"], "as_of": raw["as_of"],
            "as_of_text": raw["as_of"].replace("R08年", "令和8年").replace("R09年", "令和9年")}


def as_of_label(c: dict) -> str:
    """'令和8年7月末の暫定値'."""
    return f"{c['as_of_text']}の暫定値"


def ranking_page(page, c: dict, tabs) -> str:
    cur, done, prev = c["cur"], c["done"], c["years"][-3]
    by = c["by"]
    rows = [[str(c["rank"][p]), f'<a href="/{pf.SLUG[p]}/">{esc(pf.full(p))}</a>', n(by[p][done][0]), n(by[p][done][1]), n(by[p][done][2]),
             n(by[p][prev][0]), n(by[p][cur][0])] for p in c["ranked"]]
    head = ["順位", "道府県", f"{fy_label(done)} 計", "捕殺", "非捕殺", f"{fy_label(prev)} 計", f"{fy_label(cur)}({c['as_of_text']}まで)"]
    nat = c["national"]
    nat_rows = [[fy_label(y) + ("(暫定)" if y == cur else ""), n(nat[y][0]), n(nat[y][1]), n(nat[y][2]),
                 n(c["species"]["ツキノワグマ"][y][0]), n(c["species"]["ヒグマ"][y][0])] for y in reversed(c["years"])]
    ys = [y for y in c["years"] if y != cur]
    chart = charts.bars([short_label(y) for y in ys], [nat[y][0] for y in ys],
                        title="許可捕獲数(頭)", desc=f"全国のクマ類の許可捕獲数(頭)。平成20年度から{fy_label(done)}まで。{fy_label(cur)}は{c['as_of_text']}までの暫定値のため、除いています",
                        uid="cap", marks=[nat[y][2] for y in ys], marks_label="うち非捕殺(放獣など)")
    top = c["ranked"][0]
    body = f"""{crumbs([("全国", "/"), ("ランキング", "/ranking/sightings/"), ("許可捕獲数", None)])}
<h1>クマの許可捕獲数ランキング({fy_label(done)}・環境省の速報値)</h1>
<p class="lead">{fy_label(done)}の全国のクマ類の許可捕獲数は{n(nat[done][0])}頭で、{esc(pf.full(top))}が{n(by[top][done][0])}頭で最も多くなっています。{fy_label(prev)}は{n(nat[prev][0])}頭で、{fy_label(done)}は{ratio_text(nat[done][0], nat[prev][0])}です。</p>
{tabs("captures")}
<h2>全国の推移(平成20年度から)</h2>
{chart}
{table(["年度", "計", "捕殺", "非捕殺", "うちツキノワグマ", "うちヒグマ"], nat_rows)}
<h2>道府県別({fy_label(done)}の多い順)</h2>
{table(head, rows)}
<p class="notice">{NOTE}{fy_label(cur)}は、{c['as_of_text']}までの暫定値です。{NOT_LISTED}</p>
<p class="notice">出典: 環境省「クマ類の捕獲数(許可捕獲数)について[速報値]」(<a href="{esc(c['raw']['source_page'])}" rel="noopener" target="_blank">環境省「クマに関する各種情報・取組」</a>)を加工して作成。環境省が作成したものではありません。環境省の更新日: {jp_date(c['updated'])}。</p>"""
    return page(path="/ranking/captures/", title=f"クマの許可捕獲数ランキング({fy_label(done)}・道府県別・環境省の速報値)",
                description=f"{fy_label(done)}のクマ類の許可捕獲数は全国で{n(nat[done][0])}頭。道府県別のランキングと、平成20年度からの全国の推移を、環境省の速報値からまとめています。", body=body)


def pref_block(c: dict | None, short: str, name: str) -> str:
    if not c:
        return ""
    if short not in c["by"]:
        return (f"<h2>クマ類の許可捕獲数</h2>\n<p>環境省の許可捕獲数の表には、{esc(name)}は載っていません(近年、クマの目撃・捕獲の実績がない県は、表示されていません)。"
                f'全国の数字は、<a href="/ranking/captures/">許可捕獲数ランキング</a>にあります。</p>\n')
    by, cur, done = c["by"][short], c["cur"], c["done"]
    ys = [y for y in c["years"] if y != cur][-8:]
    chart = charts.bars([short_label(y) for y in ys], [by[y][0] for y in ys], title="許可捕獲数(頭)",
                        desc=f"{name}のクマ類の許可捕獲数(頭)と、うち非捕殺の頭数", uid="pcap", marks=[by[y][2] for y in ys], marks_label="うち非捕殺(放獣など)")
    rows = [[fy_label(y) + ("(暫定)" if y == cur else ""), n(by[y][0]), n(by[y][1]), n(by[y][2])] for y in reversed(c["years"][-6:])]
    return f"""<h2>クマ類の許可捕獲数</h2>
<p>{fy_label(done)}の許可捕獲数は、{n(by[done][0])}頭(捕殺{n(by[done][1])}頭・非捕殺{n(by[done][2])}頭)で、{len(c['ranked'])}道府県中{c['rank'][short]}位でした。{fy_label(cur)}は、{c['as_of_text']}までで{n(by[cur][0])}頭です。</p>
{chart}{table(["年度", "計", "捕殺", "非捕殺"], rows)}
<p class="notice">{NOTE}{c['as_of_text']}までの暫定値を含みます。環境省の更新日: {jp_date(c['updated'])}。出典: 環境省の資料を加工して作成。<a href="/ranking/captures/">全国のランキング</a></p>
"""
