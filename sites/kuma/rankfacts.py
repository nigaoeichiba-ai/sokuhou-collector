"""Columns and sentences that the ranking pages add to the ministry's tables (2026-11-09): what the table alone does not show.

  sightings   the direction of the change in each of the last three years, and how many prefectures went up
  injuries    victims per 1,000,000 people (injuries are counted on one national standard, so the figure can be compared across prefectures)
  deaths      the five last fiscal years one by one, and how the last five compare with the five before

Sighting counts are never divided by the population: each prefecture counts them its own way.
"""
from __future__ import annotations

from sites.kuma import population as pop_mod
from sites.kuma.fmt import fy_label, jp_date, n, table

_POP: dict | None = None


def _pop() -> dict:
    global _POP
    if _POP is None:
        _POP = pop_mod.load()
    return _POP


def credit() -> str:
    return _pop()["source"]


def per_million(people: int, name: str) -> float:
    return people / _pop()["population"][name] * 1000      # the table is in thousands of people


def fy_or_h(y: str) -> str:
    return f"平成{int(y[1:])}年度" if y.startswith("H") else fy_label(y)


# ---------------------------------------------------------------- injuries

def injuries_cols(d: dict, r: dict) -> list[str]:
    done = d["done"]
    return [f"{per_million(r['inj'][done][1], r['name']):.1f}", f"{per_million(r['injured7'], r['name']):.1f}"]


def injuries_after(d: dict, rows: list[dict]) -> str:
    done = d["done"]
    ranked = sorted(rows, key=lambda r: (-per_million(r["injured7"], r["name"]), r["name"]))
    top = "、".join(f"{r['name']}({per_million(r['injured7'], r['name']):.1f}人)" for r in ranked[:3])
    by_count = {r["name"]: i for i, r in enumerate(sorted(rows, key=lambda r: (-r["injured7"], r["name"])), 1)}
    by_pop = {r["name"]: i for i, r in enumerate(ranked, 1)}
    # the prefecture whose place moves most when the population is taken into account (a prefecture with 3 or more victims, so that one person does not decide it)
    big = [r for r in rows if r["injured7"] >= 3]
    mover = max(big, key=lambda r: (by_count[r["name"]] - by_pop[r["name"]], r["name"]))
    out = [f"令和元年度から{fy_label(done)}までの7年間の被害者数を、人口100万人あたりにします。多い順に、{top}です。"]
    if by_count[mover["name"]] - by_pop[mover["name"]] >= 5:
        out.append(f"{mover['name']}は、人数では{by_count[mover['name']]}位ですが、人口あたりでは{by_pop[mover['name']]}位に上がります。")
    nat = sum(r["injured7"] for r in rows)
    out.append(f"人口あたりの値は、7年間の被害者数の合計(全国{n(nat)}人)を、各都道府県の総人口で割った値です。人口は{_pop()['as_of'][:4]}年10月1日現在の1時点で、7年間は同じ人口として扱っています。"
               "被害者が数人の県は、1人増えるだけで値が大きく動きます。")
    return "<p>" + "".join(out) + "</p>\n<p class=\"notice credit\">" + _pop()["source"] + "人身被害は全国で同じ基準で数えているため、人口で割った比べ方ができます。出没件数は都道府県ごとに数え方が違うため、人口では割りません。</p>"


# ---------------------------------------------------------------- deaths

def _last5(d: dict) -> list[str]:
    return [y for y in d["inj"]["years"] if y != d["cur"]][-5:]


def deaths_trend(d: dict, r: dict) -> str:
    return " / ".join(n(r["inj"][y][2]) for y in _last5(d))


def deaths_head(d: dict) -> str:
    ys = _last5(d)
    return f"年度別({fy_label(ys[0])}から{fy_label(ys[-1])}・古い順)"


def deaths_after(d: dict, rows: list[dict]) -> str:
    ys = [y for y in d["inj"]["years"] if y != d["cur"]]
    last, before = ys[-5:], ys[-10:-5]
    nat = d["inj"]["national"]
    a, b = sum(nat[y][2] for y in last), sum(nat[y][2] for y in before)
    out = []
    if b:
        word = f"その前の5年度({fy_or_h(before[0])}から{fy_or_h(before[-1])})の{b}人を上回っています" if a > b else (f"その前の5年度の{b}人と同じです" if a == b else f"その前の5年度の{b}人より少なくなっています")
        out.append(f"直近5年度({fy_or_h(last[0])}から{fy_label(last[-1])})の全国の死亡者は合計{n(a)}人で、{word}。")
    both = [r for r in rows if sum(r["inj"][y][2] for y in last) > 0]
    often = [r for r in rows if sum(1 for y in last if r["inj"][y][2] > 0) >= 3]
    out.append(f"直近5年度に死亡者が出たのは{n(len(both))}道府県です。")
    if often:
        out.append("5年度のうち3年度以上で死亡者が出たのは、" + "・".join(r["name"] for r in often) + "です。")
    return "<p>" + "".join(out) + "</p>"


def later_deaths(d: dict, listed: dict[str, int], as_of: str) -> str:
    """The death list and the injury statistics are published on different days: put the two numbers for the year in progress side by side.
    `listed` is {prefecture: people in the list}, `as_of` the list's own date. Nothing is said about days or places the list does not have."""
    cur = d["cur"]
    stat = d["inj"]["national"][cur][2]
    total = sum(listed.values())
    when = d["inj_as_of"].replace("R08年", "令和8年")
    out = [f"上の一覧のうち{fy_label(cur)}の分は、{jp_date(as_of)}時点の{n(total)}人です。"]
    if stat == total:
        out.append(f"{when}の人身被害の統計でも、{fy_label(cur)}の死亡者は全国で{n(stat)}人で、一覧の人数と同じです。")
    else:
        word = f"一覧より{n(stat - total)}人多い数です" if stat > total else "一覧の人数とは一致していません"
        out.append(f"{when}の人身被害の統計では、{fy_label(cur)}の死亡者は全国で{n(stat)}人で、{word}。")
        more = [(r["name"], r["inj"][cur][2] - listed.get(r["name"], 0)) for r in d["rows"]]
        more = [(name, k) for name, k in more if k > 0]
        if stat > total and more:
            out.append("統計の人数が一覧より多いのは、" + "、".join(f"{name}({n(k)}人)" for name, k in more) + "です。日付と場所は、この一覧にはまだありません。")
    return f"<h2>{fy_label(cur)}の死亡者数を人身被害の統計と比べる</h2>\n<p>" + "".join(out) + "</p>"


def only_this_year(d: dict, zero: list[str]) -> str:
    """Prefectures left out of the death ranking (no death in the completed years) that do have one in the year in progress."""
    names = [r["name"] for r in d["rows"] if r["name"] in zero and r["inj"][d["cur"]][2] > 0]
    if not names:
        return ""
    return "このうち" + "・".join(names) + f"は、{fy_label(d['cur'])}(途中)に死亡者の記録があります。"


# ---------------------------------------------------------------- sightings

def _ytd_order(d: dict) -> list[dict]:
    return sorted((r for r in d["rows"] if r["has"]), key=lambda r: (-r["ytd"][d["cur"]], r["name"]))


def sightings_now_lead(d: dict) -> str:
    top = _ytd_order(d)[0]
    return f"{fy_label(d['cur'])}の{d['months'][0]}月から{d['latest_month']}月に限ると、最も多いのは{top['name']}({n(top['ytd'][d['cur']])}件)です。"


def sightings_now(d: dict) -> str:
    """The ten prefectures with the most sightings so far this year, beside the same months a year earlier."""
    cur, done = d["cur"], d["done"]
    span = f"{d['months'][0]}月から{d['latest_month']}月"
    rows = [[str(i), f'<a href="/{r["slug"]}/">{r["name"]}</a>', f'{n(r["ytd"][cur])}件', f'{n(r["ytd"][done])}件'] for i, r in enumerate(_ytd_order(d)[:10], 1)]
    return (f"<h2>{fy_label(cur)}の{span}で多い県</h2>\n"
            + table(["順位", "道府県", f"{fy_label(cur)}", f"{fy_label(done)}の同じ期間"], rows)
            + f'\n<h2>この順位は生息数の順ではありません</h2>\n<p>並べているのは出没の件数で、クマの生息数(頭数)ではありません。'
              f'生息数は調べた年や推定の方法が県ごとにそろっていないため、同じ条件で並べた都道府県のランキングは載せていません。'
              f'出没の件数も、数え方は県ごとに違います。</p>')



def _dir(new: int | None, old: int | None) -> str:
    if new is None or old is None or (not old and not new):
        return "−"
    return "増" if new > old else ("減" if new < old else "同")


def directions(d: dict, r: dict) -> list[str]:
    """[R06 against R05, R07 against R06, this year's period against the same period of last year]."""
    ys = d["years"]
    return [_dir(r["total"][ys[-3]], r["total"][ys[-4]]), _dir(r["total"][ys[-2]], r["total"][ys[-3]]), _dir(r["ytd"][d["cur"]], r["ytd"][d["done"]])]


def sightings_head(d: dict) -> str:
    ys = d["years"]
    return f"前年度からの増減の向き({fy_label(ys[-3])}・{fy_label(ys[-2])}・{fy_label(d['cur'])}の同じ期間)"


def sightings_after(d: dict, rows: list[dict]) -> str:
    ys = d["years"]
    dirs = {r["name"]: directions(d, r) for r in rows}
    steps = [(fy_label(ys[-3]), 0), (fy_label(ys[-2]), 1), (f"{fy_label(d['cur'])}の{d['months'][0]}月から{d['latest_month']}月", 2)]
    out = []
    for label, i in steps:
        up = sum(1 for v in dirs.values() if v[i] == "増")
        down = sum(1 for v in dirs.values() if v[i] == "減")
        out.append(f"{label}は、前年度(同じ期間)より増えたのが{n(up)}道府県、減ったのが{n(down)}道府県でした。")
    out.append(f"対象は{n(len(rows))}道府県です。")
    all_up = [name for name, v in dirs.items() if v == ["増", "増", "増"]]
    all_down = [name for name, v in dirs.items() if v == ["減", "減", "減"]]
    if all_up:
        out.append("3つとも増えたのは、" + "・".join(all_up) + "です。")
    if all_down:
        out.append("3つとも減ったのは、" + "・".join(all_down) + "です。")
    return "<p>" + "".join(out) + "</p>"
