"""'ランキングの読み方' under the amount and raise rankings: the two ends of the table in words, the ties, and how to use the order.  All numbers are computed from the rows."""
from __future__ import annotations


def _list(rows: list[dict], key, k) -> str:
    return "、".join(f'<a href="/{r["slug"]}/">{k.esc(r["name"])}</a>({key(r)})' for r in rows)


def notes(d: dict, kind: str, k) -> str:
    rows = d["rows"]
    label = k.esc(d["label"])
    raise_txt = lambda r: "+%d円" % r["raise"]  # noqa: E731
    yen_txt = lambda r: k.yen(r["amount"])  # noqa: E731
    if kind == "raise":
        by = sorted(rows, key=lambda r: (-r["raise"], r["name"]))
        top, bottom = by[:5], by[-5:][::-1]
        dist = {}
        for r in rows:
            dist[r["raise"]] = dist.get(r["raise"], 0) + 1
        common = max(dist, key=lambda v: (dist[v], v))
        lead = (f"<p>{label}の引上げ額が最も大きい5都道府県は、{_list(top, raise_txt, k)}です。最も小さい5都道府県は、{_list(bottom, raise_txt, k)}です。"
                f"引上げ額は+{min(dist)}円から+{max(dist)}円まで{len(dist)}通りあり、最も多いのは+{common}円の{dist[common]}都道府県です。最大と最小の差は{max(dist) - min(dist)}円です。</p>")
        use = ("<li>引上げ額の順位は、その年度に何円上がったかの順位です。最低賃金そのものが高いかどうかは、<a href=\"/ranking/high/\">金額のランキング</a>で見ます。</li>"
               "<li>引上げ額が大きくても、もともとの額が低ければ、金額の順位は低いままです。</li>"
               "<li>国の目安と比べた表は、<a href=\"/guide/r8/\">令和8年度の最低賃金は目安より何円上がったか</a>にあります。</li>")
    else:
        asc = sorted(rows, key=lambda r: (r["amount"], r["name"]))
        top, bottom = asc[::-1][:5], asc[:5]
        amounts = [r["amount"] for r in rows]
        ties = sum(1 for a in set(amounts) if amounts.count(a) > 1)
        lead = (f"<p>{label}の最低賃金が最も高い5都道府県は、{_list(top, yen_txt, k)}です。最も低い5都道府県は、{_list(bottom, yen_txt, k)}です。"
                f"最高額と最低額の差は{max(amounts) - min(amounts)}円で、1日8時間・年250日働くと、この時給の差は年に{(max(amounts) - min(amounts)) * 2000:,}円になります。"
                f"同じ額の都道府県があるのは、{len(set(amounts))}通りの額のうち{ties}通りで、同額は同じ順位にしています。</p>")
        use = ("<li>順位は、47都道府県の額を比べたものです。自分の県の順位が低くても、守る下限は、勤務先の県の額です。</li>"
               "<li>順位が1つ違っても、額は1円しか違わないことがあります。順位より、額の差を見てください。</li>"
               "<li>年度ごとの順位の動きは、<a href=\"/analysis/ranks/\">順位が上がった県・下がった県</a>にあります。</li>")
    return f"""<h2>ランキングの読み方</h2>
{lead}
<ul>
{use}
<li>額は、その年度に決まった地域別最低賃金(時間額)です。発効日の前は、その県では1つ前の年度の額が適用されています。県ごとの日付は<a href="/calendar/">発効日カレンダー</a>にあります。</li>
<li>各県の推移や、全国加重平均との差は、県ごとのページ(表の県名のリンク)にあります。</li>
</ul>
"""
