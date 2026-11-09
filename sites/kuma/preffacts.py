"""What is true of ONE prefecture, computed from the ministry's tables (Ministry of the Environment, provisional figures).

Each sentence is written only when it applies to that prefecture, so the pages differ in which sentences they carry, not only in the numbers:
  lead(d, r)          the two sentences at the top: the injuries of the last full year, and the deaths since Heisei 20
  injury_html(d, r)   the paragraph under the heading 人身被害: the history since Heisei 20
  items(d, r)         the list under "数字から言えること": the sightings over five years, the season, injuries per 1,000 sightings,
                      captures against sightings, emergency shootings, the months of the deaths
Nothing is divided by a population or an area: the sighting counts are made by each prefecture its own way, so prefectures are never ranked or
compared by a ratio built from them (the same prefecture's years are).  Injuries and deaths are counted on one national standard.
"""
from __future__ import annotations

from sites.kuma.fmt import fy_label, n, ratio_text
from sokuhou.sitekit import esc

SUMMER = (2, 3, 4)       # June-August (months start in April)
AUTUMN = (5, 6, 7)       # September-November
MIN_SEASON = 60          # a year with fewer sightings than this does not say which season is larger
MIN_RATE = 150           # a year with fewer sightings than this moves too much with one person for a per-1,000 figure
MIN_CAPTURE = 100        # sightings needed in both years for the capture-to-sightings comparison
MIN_YTD = 30             # the same period of the last year must have this many sightings for a comparison


def fy_or_h(y: str) -> str:
    return f"平成{int(y[1:])}年度" if y.startswith("H") else fy_label(y)


def _full_years(d: dict) -> list[str]:
    """The fiscal years that are complete in the injury table (the current one is partial)."""
    return [y for y in d["inj"]["years"] if y != d["cur"]]


def _pct(a: float, b: float) -> str:
    return f"{round(a / b * 100)}%"


def _bai(a: int, b: int) -> str:
    return f"約{a / b:.1f}倍"


def _times(new: int, old: int) -> str:
    """'の約2.4倍' / 'から35%減' / 'と同じ' appended to 'the same period of last year (N)'."""
    t = ratio_text(new, old)
    if t == "同じ":
        return "と同じ件数"
    return f"の{t}" if "倍" in t else f"から{t}"


# ---------------------------------------------------------------- the lead: injuries and deaths

def lead(d: dict, r: dict) -> list[str]:
    done, name = d["done"], r["name"]
    a, p, dead = r["inj"][done]
    rank = r["rank"]["injured"]
    years = _full_years(d)
    first = years[0]
    out = []
    if p:
        out.append(f"{esc(name)}の{fy_label(done)}の人身被害は、{n(a)}件・{n(p)}人(うち死亡{n(dead)}人)で、39道府県中{rank}位(人数)でした。")
    else:
        k = [y for y in years if r["inj"][y][1] > 0]
        if k:
            out.append(f"{esc(name)}の{fy_label(done)}は、人身被害の記録がありません。直近の人身被害は{fy_or_h(k[-1])}({n(r['inj'][k[-1]][1])}人)です。")
        else:
            out.append(f"{esc(name)}は、{fy_or_h(first)}から{fy_label(done)}まで、人身被害の記録がありません。")
    dead_by = {y: r["inj"][y][2] for y in d["inj"]["years"]}
    total_dead = sum(dead_by.values())
    if total_dead:
        yrs = [y for y in d["inj"]["years"] if dead_by[y] > 0]
        top = max(yrs, key=lambda y: (dead_by[y], y))
        extra = f"最も多かったのは{fy_or_h(top)}の{n(dead_by[top])}人です。" if len(yrs) > 1 and dead_by[top] > 1 else f"最後は{fy_or_h(yrs[-1])}です。"
        out.append(f"{fy_or_h(first)}以降の死亡者は、合計{n(total_dead)}人です。{extra}")
    else:
        out.append(f"{fy_or_h(first)}以降、死亡者の記録はありません。")
    return out


# ---------------------------------------------------------------- the injury history

def injury_html(d: dict, r: dict) -> str:
    """The paragraph under 人身被害: the years since Heisei 20 in one view (the last full year and its rank are in the lead)."""
    years = _full_years(d)
    first, last = years[0], years[-1]
    cases = sum(r["inj"][y][0] for y in years)
    people = sum(r["inj"][y][1] for y in years)
    out = []
    if people:
        top = max(years, key=lambda y: (r["inj"][y][1], y))
        with_inj = [y for y in years if r["inj"][y][1] > 0]
        out.append(f"{fy_or_h(first)}から{fy_label(last)}までの人身被害は、合計{n(cases)}件・{n(people)}人です。被害があった年度は{n(len(years))}のうち{n(len(with_inj))}で、最も多かったのは{fy_or_h(top)}({n(r['inj'][top][1])}人)です。")
        recent, before = years[-5:], years[-10:-5]
        rs, bs = sum(r["inj"][y][1] for y in recent), sum(r["inj"][y][1] for y in before)
        if rs == 0 and bs > 0:
            out.append(f"直近5年度({fy_or_h(recent[0])}から{fy_label(recent[-1])})は、人身被害がありません。その前の5年度は{n(bs)}人でした。")
        elif bs > 0:
            out.append(f"直近5年度({fy_or_h(recent[0])}から{fy_label(recent[-1])})の合計は{n(rs)}人で、その前の5年度({n(bs)}人){_times(rs, bs)}です。")
        elif rs > 0:
            out.append(f"直近5年度の合計は{n(rs)}人です。その前の5年度は、人身被害がありません。")
        c = d["cur"]
        cur = r["inj"][c]
        out.append(f"{fy_label(c)}は、{esc(d['inj_as_of'].replace('R08年', '令和8年'))}までで{n(cur[0])}件・{n(cur[1])}人(うち死亡{n(cur[2])}人)です。")
    else:
        out.append(f"{fy_or_h(first)}から{fy_label(last)}まで、人身被害の記録はありません。")
    return "<p>" + "".join(out) + "</p>"


# ---------------------------------------------------------------- the list

def _sightings(d: dict, r: dict) -> list[str]:
    if not r["has"]:
        return []
    full = [y for y in d["years"] if y != d["cur"]]
    tot = {y: r["total"][y] for y in full}
    if any(v is None for v in tot.values()):
        return []
    done, cur = d["done"], d["cur"]
    top = max(full, key=lambda y: (tot[y], y))
    low = min(full, key=lambda y: (tot[y], y))
    out = []
    if tot[low] > 0 and tot[top] > tot[low]:
        if top == done:
            out.append(f"{fy_label(done)}の{n(tot[done])}件は、{fy_label(full[0])}以降で最も多い件数です。最も少なかった{fy_label(low)}({n(tot[low])}件)の{_bai(tot[top], tot[low])}にあたります。")
        else:
            out.append(f"{fy_label(full[0])}以降で出没が最も多かったのは{fy_label(top)}({n(tot[top])}件)です。{fy_label(done)}は、その{_pct(tot[done], tot[top])}にあたる{n(tot[done])}件でした。")
    ytd_cur, ytd_done = r["ytd"][cur], r["ytd"][done]
    if ytd_done and ytd_done >= MIN_YTD:
        x = ytd_cur / ytd_done
        if x >= 1.5 or x <= 0.67:
            out.append(f"{fy_label(cur)}の{d['months'][0]}月から{d['latest_month']}月は{n(ytd_cur)}件で、前年度の同じ期間({n(ytd_done)}件){_times(ytd_cur, ytd_done)}です。")
    return out


def _season(d: dict, r: dict) -> list[str]:
    if not r["has"]:
        return []
    ys = [y for y in d["years"] if y != d["cur"]]
    share = {}
    for y in ys:
        m = r["monthly"][y]
        t = r["total"][y]
        if any(v is None for v in m) or not t or t < MIN_SEASON:
            return []
        share[y] = (sum(m[i] for i in SUMMER) / t * 100, sum(m[i] for i in AUTUMN) / t * 100)
    autumn_years = [y for y in ys if share[y][1] > share[y][0]]
    k, done = len(ys), d["done"]
    s, a = share[done]
    tail = f"{fy_label(done)}は、9〜11月が{round(a)}%、6〜8月が{round(s)}%でした。"
    if len(autumn_years) == k:
        return [f"{n(k)}年度のすべてで、9〜11月の件数が6〜8月を上回りました。{tail}"]
    if not autumn_years:
        return [f"{n(k)}年度のすべてで、6〜8月の件数が9〜11月を上回りました。{tail}"]
    names = "・".join(fy_label(y) for y in autumn_years)
    return [f"9〜11月が6〜8月を上回ったのは、{n(k)}年度のうち{n(len(autumn_years))}年度({names})です。年度によって、ピークの時期が入れ替わっています。{tail}"]


def _rate(d: dict, r: dict) -> list[str]:
    if not r["has"]:
        return []
    ys = [y for y in d["years"] if y != d["cur"]]
    rate = {}
    for y in ys:
        t = r["total"][y]
        if t is None or t < MIN_RATE:
            return []
        rate[y] = r["inj"][y][1] / t * 1000
    if not any(rate.values()):
        return []
    top = max(ys, key=lambda y: (rate[y], y))
    series = "、".join(f"{fy_label(y)}が{rate[y]:.1f}人" for y in ys)
    return [f"出没1,000件あたりの被害者数は、{series}です。最も高かったのは{fy_label(top)}です。出没件数の数え方は県ごとに違うため、この比べ方は同じ県の年度どうしにだけ使えます。"]


def _capture(d: dict, r: dict) -> list[str]:
    c = d.get("captures")
    if not c or not r["has"] or r["short"] not in c["by"]:
        return []
    by, done = c["by"][r["short"]], c["done"]
    prev = c["years"][-3]
    s_done, s_prev = r["total"][done], r["total"][prev]
    if not s_done or not s_prev or s_done < MIN_CAPTURE or s_prev < MIN_CAPTURE:
        return []
    p_done, p_prev = by[done][0], by[prev][0]
    return [f"{fy_label(done)}の許可捕獲は{n(p_done)}頭で、出没件数({n(s_done)}件)の{_pct(p_done, s_done)}にあたります。{fy_label(prev)}は{n(p_prev)}頭で{_pct(p_prev, s_prev)}でした。頭数と件数は数え方が違うため、同じ県の年度どうしの比べです。"]


def _emergency(d: dict, r: dict) -> list[str]:
    name = r["name"]
    done, cur = d["done"], d["cur"]
    k = {y: sum(1 for x in d["emergency"][y]["cases"] if x["prefecture"] == name) for y in (done, cur)}
    if not any(k.values()):
        return []
    return [f"環境省が把握する緊急銃猟は、{fy_label(done)}が{n(k[done])}件、{fy_label(cur)}が{n(k[cur])}件です。"]


def _death_months(d: dict, r: dict) -> list[str]:
    name = r["name"]
    inc = [i for y in (d["done"], d["cur"]) for i in d["fatal"][y]["incidents"] if i["prefecture"] == name]
    if len(inc) < 2:
        return []
    months = sorted({int(i["date"][5:7]) for i in inc})
    return [f"環境省の一覧にある死亡事故{n(len(inc))}件が起きた月は、{'・'.join(f'{m}月' for m in months)}です。"]


def items(d: dict, r: dict) -> list[str]:
    out: list[str] = []
    for f in (_sightings, _season, _rate, _capture, _emergency, _death_months):
        out += f(d, r)
    return out


def section_html(d: dict, r: dict) -> str:
    xs = items(d, r)
    if not xs:
        return ""
    return f"<h2>{esc(r['name'])}の数字から言えること</h2>\n<ul>\n" + "\n".join(f"<li>{x}</li>" for x in xs) + "\n</ul>\n"
