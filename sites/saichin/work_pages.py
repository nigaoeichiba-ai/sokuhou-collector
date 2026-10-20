"""Two guides for people who work for an hourly wage, built from the site's own minimum-wage numbers.

/guide/wall/  how many hours a week at the minimum wage reach the social-insurance line (20 hours) and the 1.3 million yen dependant line, per prefecture.
/guide/raise/ how to look at one's hourly pay: against the minimum wage, in a job ad, and what a rise of the minimum wage does and does not change.
Statements about the rules are limited to what the cited pages say (read in a browser on 2026-10-20); every number is computed from the prefectures' amounts.
`k` is the build module (esc, yen, crumbs helpers are not needed here: the guide page supplies the frame).
"""
from __future__ import annotations

from sites.saichin.analysis import raise_series

WEEKS = 52
LINE_HOURS = 20                  # the weekly scheduled hours at which social insurance applies (Ministry / Japan Pension Service)
DEPENDANT_LINE = 1_300_000       # annual income at which a dependant (spouse etc.) loses that status (Ministry)
SOCIAL_INSURANCE_OLD_MONTHLY = 88_000   # the monthly wage requirement abolished on 2026-10-01


def annual(w: int, hours: float = LINE_HOURS) -> int:
    return round(w * hours * WEEKS)


def monthly(w: int, hours: float = LINE_HOURS) -> int:
    return round(w * hours * WEEKS / 12 / 100) * 100


def man(yen: int) -> str:
    return f"{yen / 10000:.1f}万円"


def hours_for(target: int, w: int) -> float:
    return target / (WEEKS * w)


def wall_rows(d: dict) -> list[dict]:
    out = []
    for r in sorted(d["rows"], key=lambda r: (-r["amount"], r["name"])):
        a = annual(r["amount"])
        out.append({"row": r, "w": r["amount"], "annual": a, "monthly": monthly(r["amount"]), "hours130": hours_for(DEPENDANT_LINE, r["amount"]),
                    "over": a > DEPENDANT_LINE})
    return out


def wall_body(d: dict, k) -> str:
    rows = wall_rows(d)
    lo, hi = rows[-1], rows[0]
    over = [x["row"]["name"] for x in rows if x["over"]]
    short = [x for x in rows if not x["over"]]
    near = max(short, key=lambda x: x["annual"]) if short else None
    fl = d["label"]
    trs = "".join(
        f'<tr><td><a href="/{x["row"]["slug"]}/">{k.esc(x["row"]["name"])}</a></td><td>{k.yen(x["w"])}</td><td>{k.yen(x["monthly"])}</td>'
        f'<td>{man(x["annual"])}</td><td>{x["hours130"]:.1f}時間</td><td>{"超える" if x["over"] else "超えない"}</td></tr>'
        for x in rows)
    over_text = ("、".join(over[:-1]) + "と" + over[-1]) if len(over) > 1 else (over[0] if over else "")
    over_sentence = (f"週20時間で130万円を超えるのは、{k.esc(over_text)}です。" if over else "週20時間で130万円を超える都道府県はありません。")
    return f"""<p>2026年10月1日に、社会保険の「月額8.8万円以上」という賃金の要件がなくなりました(年収106万円の壁と呼ばれていたものです)。いま分かれ目になるのは、週の所定労働時間が20時間以上か、そして配偶者などの扶養に入る年収130万円です。{k.esc(fl)}の最低賃金で週20時間働くと、年収は{k.esc(lo['row']['name'])}の{man(lo['annual'])}から{k.esc(hi['row']['name'])}の{man(hi['annual'])}までです。</p>
<h2>いま何が変わったか</h2>
<p>短時間労働者が社会保険(健康保険・厚生年金保険)に入る要件のうち、所定内賃金が月額8.8万円以上という賃金要件は、2026年10月1日に撤廃されました(日本年金機構)。残っている要件は次のとおりです。</p>
<ul>
<li>週の所定労働時間が20時間以上であること</li>
<li>勤め先が従業員数51人以上の企業であること(企業規模の要件。厚生労働省は、10年かけて段階的に縮小・撤廃するとしています)</li>
<li>学生ではないこと</li>
</ul>
<p>厚生労働省の説明では、週の所定労働時間が20時間未満なら、原則として社会保険の加入対象になりません。残業などで一時的に20時間以上になっても加入しませんが、週20時間以上の状態が2か月を超えて続くときは、加入対象になることがあります。</p>
<h2>最低賃金で週20時間働いたときの年収と、130万円に届く時間</h2>
<p>{k.esc(fl)}の最低賃金ちょうどで、週20時間、年52週働いたとして計算しました。{over_sentence}{f"130万円に最も近いのに届かないのは{k.esc(near['row']['name'])}で、{man(near['annual'])}です。" if near else ""}</p>
<div class="tablewrap"><table><thead><tr><th>都道府県</th><th>最低賃金</th><th>週20時間の月収</th><th>週20時間の年収</th><th>130万円に届く週の時間</th><th>週20時間で130万円を</th></tr></thead><tbody>{trs}</tbody></table></div>
<h2>130万円の壁</h2>
<p>厚生労働省の説明では、年収が130万円以上になると、配偶者の扶養(第3号被保険者)から外れます。週20時間未満で働く場合でも同じで、国民年金と国民健康保険の保険料がかかります。収入が一時的に上がった場合は、事業主の証明により、引き続き扶養が認められる特例があります。</p>
<p>上の表の「130万円に届く週の時間」は、最低賃金ちょうどで働くとき、週に何時間で年収が130万円になるかです。たとえば{k.esc(hi['row']['name'])}では約{hi['hours130']:.1f}時間、{k.esc(lo['row']['name'])}では約{lo['hours130']:.1f}時間です。時給が最低賃金より高い人は、これより少ない時間で届きます。</p>
<h2>数え方と注意</h2>
<ul>
<li>年収は「最低賃金 × 週の時間 × 52週」です。賞与、残業代、通勤手当は入れていません。税金と社会保険料を引く前の額です。</li>
<li>月収は、年収を12で割って100円未満を四捨五入した額です。</li>
<li>扶養の判定は、収入の範囲や数え方が、加入している健康保険や勤め先で違うことがあります。実際の判断は、勤め先、健康保険組合、年金事務所にご確認ください。</li>
<li>所得税・住民税がかかる年収の目安は、税制の改正で変わっています。ここでは扱っていません。国税庁のページでご確認ください。</li>
<li>厚生労働省は、賃金要件の撤廃を、全国の最低賃金が1,016円以上になることを見極めて判断するとしていました。最低賃金1,016円以上の地域で週20時間以上働くと、年額換算で約106万円です。{k.esc(fl)}の最低賃金が最も低いのは{k.esc(lo['row']['name'])}の{k.yen(lo['w'])}で、{"全47都道府県が1,016円以上です" if lo['w'] >= 1016 else "1,016円に届かない都道府県があります"}。</li>
</ul>
<p>自分の給料が最低賃金を下回っていないかは、<a href="/check/">差額チェッカー</a>で計算できます。時給に直す方法は<a href="/guide/calculate/">月給・日給の換算</a>をご覧ください。</p>
"""


def raise_body(d: dict, k) -> str:
    rs = raise_series(d)[-5:]
    last = rs[-1]
    trs = "".join(
        f"<tr><td>{k.esc(x['label'])}</td><td>+{x['avg_up']}円</td><td>{x['avg_up'] / round(next(y['avg'] for y in d['years'] if y['fy'] == x['fy'] - 1)) * 100:.1f}%</td>"
        f"<td>+{round(x['avg_up'] * LINE_HOURS * WEEKS / 12):,}円</td></tr>" for x in rs)
    regions = []
    for slug, rname, shorts in k.REGIONS:
        members = [r for r in d["rows"] if r["short"] in shorts]
        hi, lo = max(members, key=lambda r: (r["amount"], r["name"])), min(members, key=lambda r: (r["amount"], r["name"]))
        regions.append((hi["amount"] - lo["amount"], slug, rname, hi, lo))
    regions.sort(key=lambda t: (-t[0], t[2]))
    rtr = "".join(
        f'<tr><td><a href="/area/{slug}/">{k.esc(rname)}</a></td><td>{k.esc(hi["name"])} {k.yen(hi["amount"])}</td><td>{k.esc(lo["name"])} {k.yen(lo["amount"])}</td><td>{diff}円</td></tr>'
        for diff, slug, rname, hi, lo in regions)
    top = regions[0]
    gap_all = max(r["amount"] for r in d["rows"]) - min(r["amount"] for r in d["rows"])
    return f"""<p>最低賃金が上がっても、最低賃金より高い時給が自動で上がるわけではありません。法律が求めているのは、時給が最低賃金額以上であることです。時給を上げたいときは、いまの時給を最低賃金と比べるところから始めます。{k.esc(last['label'])}は、全国加重平均で+{last['avg_up']}円の引上げでした。</p>
<h2>1. いまの時給を、最低賃金と比べる</h2>
<ol>
<li>勤務先がある都道府県の最低賃金を調べます(<a href="/">全国の一覧</a>)。派遣で働くときは、派遣先の事業場がある都道府県の額です。</li>
<li>給与明細の時給(月給・日給は時間額に直した額)から、通勤手当、残業代など、最低賃金の対象にならない賃金を除きます(<a href="/guide/excluded/">対象にならない賃金</a>)。</li>
<li>差額を<a href="/check/">差額チェッカー</a>で確かめます。最低賃金の発効日以降は、賃金の計算期間の途中でも、改定後の額以上を払う必要があります(厚生労働省「よくあるご質問」)。</li>
</ol>
<h2>2. 最低賃金が上がった年に、何が変わるか</h2>
<p>最低賃金ちょうどの時給で働く人は、引上げ額の分だけ時給が上がります。直近5年度の全国加重平均の引上げ額と、週20時間働いた場合の月収の増え方です。</p>
<div class="tablewrap"><table><thead><tr><th>年度</th><th>全国加重平均の引上げ額</th><th>引上げ率</th><th>週20時間の月収の増え(最低賃金ちょうどの人)</th></tr></thead><tbody>{trs}</tbody></table></div>
<p>最低賃金より高い時給の人は、勤め先が時給を見直さなければ、最低賃金との差が縮まります。たとえば、時給が最低賃金より30円高い人を考えます。最低賃金が全国加重平均と同じ+{last['avg_up']}円上がると、{'時給は新しい最低賃金を下回ります。勤め先は時給を引き上げなければなりません' if last['avg_up'] > 30 else f"差は{30 - last['avg_up']}円に縮まります"}。時給の見直しを相談するときは、現在の時給、勤務先の都道府県の最低賃金と発効日、働く時間と仕事の内容を、手元にそろえておきます。</p>
<h2>3. 求人の時給を、最低賃金と比べる</h2>
<ul>
<li><strong>固定残業代が入っていないか</strong>: 固定残業代は、一定時間分の時間外・休日・深夜の割増賃金を、定額で払うものです。若者雇用促進法にもとづく指針は、求人の賃金に固定残業代を含めるとき、適切に表示するよう求めています。割増賃金は最低賃金の対象にならないので、含まれているときは、その分を除いた時給で比べます。取り扱いは契約の内容で変わることがあります。</li>
<li><strong>試用期間の時給は</strong>: 試用期間中でも、最低賃金は適用されます。減額が認められるのは、使用者が都道府県労働局長の許可を受けた場合に限られます。</li>
<li><strong>月給の求人は</strong>: 月給を、1か月平均所定労働時間で割った時間額に直して比べます(<a href="/guide/calculate/">換算のしかた</a>)。</li>
<li><strong>勤務地は</strong>: 最低賃金は、働く事業場がある都道府県で決まります。</li>
</ul>
<h2>4. 通勤できる範囲で、地方内の違いを知る</h2>
<p>同じ地方の中でも、最低賃金には差があります。全国では最高と最低で{gap_all}円、地方の中で最も差が大きいのは{k.esc(top[2])}の{top[0]}円です。県境をまたいで通える範囲に仕事があるときは、勤務地が変わると下限が変わります。ただし、最低賃金は下限です。実際の時給は求人ごとに違い、最低賃金の差がそのまま時給の差になるとは限りません。</p>
<div class="tablewrap"><table><thead><tr><th>地方</th><th>最も高い</th><th>最も低い</th><th>差</th></tr></thead><tbody>{rtr}</tbody></table></div>
<h2>5. 相談したいとき</h2>
<p>時給が最低賃金を下回っているときは、まず使用者に伝えます。解決しないときは、最寄りの労働基準監督署に相談します(厚生労働省)。働く時間と社会保険や扶養の関係は、<a href="/guide/wall/">最低賃金で働くと、週何時間で壁に届くか</a>をご覧ください。</p>
"""


BODIES = {"wall": wall_body, "raise": raise_body}
