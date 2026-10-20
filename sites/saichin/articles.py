"""Three articles that answer what Search Console shows people asking (2026-10-20): 2026 amounts and rankings, "月給", and "大阪市・福岡市 ... の最低賃金".

/guide/r8/       how the Reiwa 8 revision came about (guideline -> local decisions -> effective dates) and how far each prefecture went past the guideline.
/guide/monthly/  the monthly pay that equals the minimum wage, per prefecture, and how to read a job ad that gives a monthly salary.
/guide/city/     the minimum wage is the prefecture's, not the city's: the big cities and the prefecture amount they share.
Statements about the process are what the Ministry's two press releases say (read in a browser on 2026-10-20); every number is computed from the prefectures' amounts.
"""
from __future__ import annotations

from sites.saichin.analysis import raise_series
from sites.saichin.places import PLACES

# The guideline ranks and amounts of Reiwa 8, from the Ministry's press release of 2026-07-28 (newpage_74920).
RANKS = {
    "A": ("埼玉 千葉 東京 神奈川 愛知 大阪".split(), 54),
    "B": ("北海道 宮城 福島 茨城 栃木 群馬 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 三重 滋賀 京都 兵庫 奈良 和歌山 島根 岡山 広島 山口 徳島 香川 愛媛 福岡".split(), 56),
    "C": ("青森 岩手 秋田 山形 鳥取 高知 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄".split(), 56),
}
RANK_OF = {s: rk for rk, (shorts, _) in RANKS.items() for s in shorts}
GUIDELINE = {rk: amount for rk, (_, amount) in RANKS.items()}
GUIDELINE_AVERAGE = (1176, 55, 4.9)          # the national weighted average, rise and rate if every prefecture followed the guideline
# Reiwa 8 decisions as the press release of 2026-09-03 counts them: {rise: number of prefectures}
DECIDED_DISTRIBUTION = {65: 1, 64: 1, 63: 2, 62: 2, 61: 4, 60: 4, 59: 5, 58: 4, 57: 7, 56: 11, 55: 3, 54: 3}


def _t(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def r8_body(d: dict, k) -> str:
    rows = sorted(d["rows"], key=lambda r: (-(r["raise"] - GUIDELINE[RANK_OF[r["short"]]]), -r["raise"], r["name"]))
    over = [r for r in rows if r["raise"] > GUIDELINE[RANK_OF[r["short"]]]]
    same = [r for r in rows if r["raise"] == GUIDELINE[RANK_OF[r["short"]]]]
    under = [r for r in rows if r["raise"] < GUIDELINE[RANK_OF[r["short"]]]]
    top = rows[0]
    avg = round(d["avg"])
    dist = {}
    for r in d["rows"]:
        dist[r["raise"]] = dist.get(r["raise"], 0) + 1
    lo, hi = min(r["raise"] for r in d["rows"]), max(r["raise"] for r in d["rows"])
    fl = d["label"]
    trs = []
    for r in rows:
        guide = GUIDELINE[RANK_OF[r["short"]]]
        diff = r["raise"] - guide
        trs.append([f'<a href="/{r["slug"]}/">{k.esc(r["name"])}</a>', RANK_OF[r["short"]], f"+{guide}円", f"+{r['raise']}円",
                    (f"+{diff}円" if diff > 0 else f"{diff}円" if diff < 0 else "同じ"), k.yen(r["amount"]), k.jp_date(r["effective_date"])])
    ranks_rows = [[rk, f"{len(shorts)}都道府県", f"+{amount}円", "、".join(k.esc(next(x["name"] for x in d["rows"] if x["short"] == s)) for s in shorts)] for rk, (shorts, amount) in RANKS.items()]
    first_date = min(r["effective_date"] for r in d["rows"])
    last_date = max(r["effective_date"] for r in d["rows"])
    n_first = sum(1 for r in d["rows"] if r["effective_date"] == first_date)
    return f"""<p>{k.esc(fl)}({d['rows'][0]['history'][-1]['fy']}年度)の地域別最低賃金は、全国加重平均で{avg:,}円(+{avg - round(d['avg_prev'])}円)になりました。47都道府県の引上げ額は+{lo}円から+{hi}円で、国の目安を上回った都道府県は{len(over)}、同じは{len(same)}、下回ったのは{len(under)}です。最も上乗せが大きかったのは{k.esc(top['name'])}で、目安より{top['raise'] - GUIDELINE[RANK_OF[top['short']]]}円多い+{top['raise']}円です。</p>
<h2>決まるまでの経過</h2>
<ol>
<li><strong>6月26日</strong>: 第74回中央最低賃金審議会で、厚生労働大臣が今年度の目安を諮問しました。同じ日に目安に関する小委員会が置かれ、6回の審議を重ねました。</li>
<li><strong>7月28日</strong>: 第75回中央最低賃金審議会が、目安を答申しました。都道府県をAからCの3つのランクに分け、引上げ額の目安は、Aランクが54円、Bランクが56円、Cランクが56円です。目安どおりに引き上げた場合の全国加重平均は{GUIDELINE_AVERAGE[0]:,}円(+{GUIDELINE_AVERAGE[1]}円、{GUIDELINE_AVERAGE[2]}%)でした。</li>
<li><strong>7月28日以降</strong>: 各都道府県の地方最低賃金審議会が、目安を参考に、地域の賃金の実態調査や参考人の意見も踏まえて審議し、改定額を答申しました。</li>
<li><strong>9月3日</strong>: 全47都道府県の答申が出そろい、厚生労働省が取りまとめました。全国加重平均は1,177円(+56円)で、目安制度が始まった昭和53年度以降で2番目の大きさです(厚生労働省)。</li>
<li><strong>10月1日〜12月2日</strong>: 関係する労働者・使用者の異議申出の手続を経て、都道府県労働局長が決定し、順次発効します。{k.jp_date(first_date)}に{n_first}都道府県、最も遅いのは{k.jp_date(last_date)}です(<a href="/calendar/">発効日カレンダー</a>)。</li>
</ol>
<h2>目安のランク</h2>
<p>目安は、都道府県の経済の実態に応じて、3つのランクに分けて示されます。{k.esc(fl)}の分け方は、次のとおりです。</p>
{_t(["ランク", "都道府県の数", "引上げ額の目安", "都道府県"], ranks_rows)}
<h2>目安より何円上がったか(47都道府県)</h2>
<p>決定した引上げ額から、その都道府県のランクの目安を引いた額です。国の目安は、都道府県が守る下限ではなく、地方の審議会が参考にする額です。{k.esc(top['name'])}のように目安を上回る都道府県も、目安どおりの都道府県もあります。</p>
{_t(["都道府県", "ランク", "目安", "決定した引上げ額", "目安との差", "最低賃金", "発効日"], trs)}
<h2>引上げ額の分布</h2>
<p>引上げ額ごとの都道府県の数です。厚生労働省の答申の取りまとめと同じ数え方です。</p>
{_t(["引上げ額", "都道府県の数"], [[f"+{a}円", f"{dist[a]}"] for a in sorted(dist, reverse=True)])}
<h2>数え方と注意</h2>
<ul>
<li>目安の額、ランク、日付、答申の件数は、厚生労働省の報道発表資料(2026年7月28日、9月3日)によります。表の最低賃金と引上げ額は、厚生労働省「地域別最低賃金の全国一覧」の値です。</li>
<li>「目安との差」は、このサイトの計算です。目安より多く上げた理由は、ここでは調べていません。各県の審議会の資料は、都道府県労働局の公表をご覧ください。</li>
<li>最高額と最低額の比率や、全国の推移は、<a href="/analysis/gap/">地域差の分析</a>と<a href="/history/">推移のページ</a>にあります。</li>
</ul>
"""


def monthly_body(d: dict, k) -> str:
    rows = sorted(d["rows"], key=lambda r: (-r["amount"], r["name"]))
    trs = []
    for r in rows:
        a = r["amount"]
        low = -(-(a * 2000) // 1200) * 100
        trs.append([f'<a href="/{r["slug"]}/">{k.esc(r["name"])}</a>', k.yen(a), k.yen(a * 8), k.yen(round(a * 40 * 52 / 12 / 100) * 100),
                    k.yen(round(a * 30 * 52 / 12 / 100) * 100), k.yen(round(a * 20 * 52 / 12 / 100) * 100), k.yen(low)])
    hi, lo = rows[0], rows[-1]
    ex = next(r for r in rows if r["short"] == "東京")
    ex_hourly = 200_000 / (2000 / 12)
    low_of = lambda r: -(-(r["amount"] * 2000) // 1200) * 100  # noqa: E731
    verdict = "上回ります" if ex_hourly >= ex["amount"] else "下回ります"
    return f"""<p>最低賃金は時間額で決まっています。月給の求人は、1か月の平均の所定労働時間で割って、時間額に直してから比べます。1日8時間・年250日の勤務なら、1か月の平均の所定労働時間は 2,000 ÷ 12 ≒ 166.7時間です。{k.esc(d['label'])}は、手当を除いた月給が、{k.esc(lo['name'])}で{k.yen(low_of(lo))}、{k.esc(hi['name'])}で{k.yen(low_of(hi))}を下回ると、最低賃金を下回ります。</p>
<h2>47都道府県の月給換算の早見表</h2>
<p>最低賃金ちょうどで働いたときの、日給(8時間)と月収です。月収は「最低賃金 × 週の時間 × 52週 ÷ 12か月」を100円未満で四捨五入した額で、週40時間、週30時間、週20時間の3通りです。右端の「月給の最低ライン」は、1日8時間・年250日の勤務で、基本給などの月給がこの額を下回ると、最低賃金を下回る額です(100円未満は切り上げ)。</p>
{_t(["都道府県", "最低賃金", "日給(8時間)", "月収(週40時間)", "月収(週30時間)", "月収(週20時間)", "月給の最低ライン"], trs)}
<h2>月給の求人を時給に直す手順</h2>
<ol>
<li><strong>月給から、最低賃金の対象にならない賃金を除きます。</strong>通勤手当、家族手当、精皆勤手当、賞与、残業代(時間外・休日・深夜の割増賃金)などは、除いて計算します(<a href="/guide/excluded/">対象にならない賃金</a>)。</li>
<li><strong>1か月の平均の所定労働時間を出します。</strong>「1日の所定労働時間 × 1年の所定労働日数 ÷ 12」です。1日8時間・年250日なら166.7時間、1日7時間・年240日なら140時間です。</li>
<li><strong>月給 ÷ 平均の所定労働時間 ≧ 勤務地の最低賃金かを比べます。</strong></li>
</ol>
<h2>計算例</h2>
<p>{k.esc(ex['name'])}(最低賃金{k.yen(ex['amount'])})で、基本給200,000円、通勤手当10,000円、1日8時間・年250日の求人を考えます。通勤手当は対象にならないので、200,000円で比べます。200,000 ÷ 166.7 ≒ {ex_hourly:,.0f}円で、最低賃金を{verdict}。</p>
<p>同じ求人で、1日7時間・年240日の場合は、月平均の所定労働時間が 7 × 240 ÷ 12 = 140時間になり、200,000 ÷ 140 ≒ {200_000 / 140:,.0f}円です。労働時間が短いと、同じ月給でも時給は高くなります。</p>
<h2>よくある間違い</h2>
<ul>
<li>通勤手当や残業代を含めた「総支給額」で比べてしまう。除いた額で比べます。</li>
<li>月給を「週40時間 × 4週」の160時間で割ってしまう。1か月は4週ちょうどではないので、年間の所定労働時間を12で割ります。</li>
<li>他の都道府県の最低賃金と比べてしまう。勤務先の事業場がある都道府県の額と比べます(派遣は派遣先の事業場がある都道府県)。</li>
<li>発効日の前に、新しい額で比べてしまう。発効日の前は改定前の額、発効日以降は新しい額です(<a href="/calendar/">発効日カレンダー</a>)。</li>
</ul>
<p>自分の給与明細で計算したいときは、<a href="/check/">差額チェッカー</a>が、手当の欄と発効日の前後の額に対応しています。計算の根拠は<a href="/guide/calculate/">月給・日給を時給に換算する方法</a>に書いています。</p>
"""


def terms_body(d: dict, k) -> str:
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    fy = d["rows"][0]["history"][-1]["fy"]
    up = round(avg[fy]) - round(avg[fy - 1])
    hi = max(d["rows"], key=lambda r: (r["amount"], r["name"]))
    lo = min(d["rows"], key=lambda r: (r["amount"], r["name"]))
    lo_names = k.esc("、".join(r["name"] for r in d["rows"] if r["amount"] == lo["amount"]))
    process = ""
    if fy == 2026:
        process = (f"<p>令和8年度の例です。7月28日に、第75回中央最低賃金審議会が、Aランク54円、Bランク56円、Cランク56円の目安を答申しました。目安どおりに上がった場合の全国加重平均は1,176円(+55円)です。"
                   f"9月3日には、全ての都道府県の答申がそろい、全国加重平均は{round(d['avg']):,}円(+{up}円)になりました。ニュースの「+{up}円」は、全国加重平均の上がり幅です。"
                   f"各県の引上げ額は、+54円から+65円まで、県によって違います。</p>")
    return f"""<p>「最賃」は、最低賃金を短くして書いた言い方です。「最低時給」という言い方もあります。最低賃金は、時間あたりの額(時間額)で定められているので、時給の形で言うと「最低時給」になります。ここでは、ニュースや求人の説明に出てくる言葉を、法律と厚生労働省の説明に合わせて整理します。</p>
<h2>最低賃金・最賃・最低時給</h2>
{_t(["言い方", "意味"], [
        ["最低賃金", "最低賃金法にもとづいて国が定める、賃金の最低額です。使用者は、この額以上の賃金を払わなければなりません(最低賃金法第4条)。"],
        ["最賃", "最低賃金を略した言い方です。"],
        ["最低時給", "時間額で定められた最低賃金を、時給の形で言った言い方です。"],
        ["時間額", "厚生労働省が使う言葉です。すべての地域別最低賃金は、時間額で定められています。"],
        ["地域別最低賃金", "都道府県ごとに1つずつ定められる最低賃金です。このサイトで扱っているのは、この額です。"],
        ["特定(産業別)最低賃金", "特定の産業について定められる、地域別より高い額の最低賃金です。両方が当てはまるときは、高い方が適用されます(第6条第1項)。"],
    ])}
<h2>ニュースに出る言葉</h2>
{_t(["言葉", "意味"], [
        ["目安", "中央最低賃金審議会が、毎年、引上げ額の参考として示す額です。都道府県をA・B・Cの3ランクに分けて、ランクごとに示します。現在は、Aランクが6都府県、Bランクが28道府県、Cランクが13県です。"],
        ["答申", "各都道府県の地方最低賃金審議会が、目安を参考に、地域の賃金実態調査などを踏まえて審議し、改定額について出す意見です。"],
        ["決定・公示", "答申を受けて、都道府県労働局長が地域別最低賃金を決め、公示します。意見の要旨の公示から15日以内に、異議を申し出られます(第11条)。"],
        ["発効日", "新しい額が効力を持つ日です。決定の公示から30日を過ぎた日か、決定で定めた日です(第14条第2項)。都道府県ごとに違います。"],
        ["全国加重平均", "47都道府県の最低賃金を、適用される労働者の数で重みづけして平均した額です。全国どこでも同じ額という意味ではありません。"],
    ])}
{process}
<h2>見間違えやすい点</h2>
<ul>
<li><strong>全国加重平均は、全国一律の額ではありません。</strong>{k.esc(d['label'])}の最低賃金は、{k.esc(hi['name'])}の{k.yen(hi['amount'])}から、{lo_names}の{k.yen(lo['amount'])}まで、{hi['amount'] - lo['amount']}円の幅があります。</li>
<li><strong>目安は、都道府県が守る下限ではありません。</strong>地方の審議会が参考にする額で、実際の改定額は、目安と同じになることも、上回ることもあります。</li>
<li><strong>「+{up}円」は、全国加重平均の上がり幅です。</strong>自分の県の上がり幅は、<a href="/ranking/raise/">引上げ額のランキング</a>で確かめます。</li>
<li><strong>発効日の前は、改定前の額です。</strong>新しい額が決まっていても、その県の発効日より前は、1つ前の額が適用されます(<a href="/calendar/">発効日カレンダー</a>)。</li>
</ul>
<h2>自分の県の最低賃金を調べる手順</h2>
<ol>
<li>働く場所(事業場)がある都道府県を確かめます。住んでいる県ではありません。派遣は、派遣先の事業場がある県です。</li>
<li><a href="/">全国の一覧</a>か、県のページで、額と発効日を見ます。</li>
<li>自分の時給を、<a href="/guide/excluded/">対象にならない賃金</a>を除いて、<a href="/guide/calculate/">時間額に換算</a>して比べます。月給の求人は、<a href="/guide/monthly/">月給換算の早見表</a>が使えます。</li>
<li>産業別の最低賃金が当てはまりそうなときは、<a href="/guide/what-is/">最低賃金とは?</a>と、厚生労働省の「特定最低賃金について」で確かめます。</li>
</ol>
<p>算出の方法や、決まる流れの詳しい説明は、<a href="/guide/how-decided/">最低賃金はどう決まる?</a>にあります。</p>
"""


# city -> prefecture (short name), chosen from the cities people ask about in Search Console and the ordinance-designated cities
CITIES = [
    ("札幌市", "北海道"), ("仙台市", "宮城"), ("さいたま市", "埼玉"), ("千葉市", "千葉"), ("横浜市", "神奈川"), ("川崎市", "神奈川"), ("新潟市", "新潟"),
    ("静岡市", "静岡"), ("浜松市", "静岡"), ("名古屋市", "愛知"), ("京都市", "京都"), ("宇治市", "京都"), ("大阪市", "大阪"), ("堺市", "大阪"), ("神戸市", "兵庫"),
    ("尼崎市", "兵庫"), ("岡山市", "岡山"), ("広島市", "広島"), ("福岡市", "福岡"), ("北九州市", "福岡"), ("熊本市", "熊本"), ("那覇市", "沖縄"),
]


def city_body(d: dict, k) -> str:
    by = {r["short"]: r for r in d["rows"]}
    trs = [[k.esc(c), f'<a href="/{by[p]["slug"]}/">{k.esc(by[p]["name"])}</a>', k.yen(by[p]["amount"]), k.jp_date(by[p]["effective_date"])] for c, p in CITIES]
    osaka, sapporo = by["大阪"], by["北海道"]
    places_rows = [[f'<a href="/{r["slug"]}/">{k.esc(r["name"])}</a>', k.esc("、".join(PLACES[r["short"]])), k.yen(r["amount"])] for r in sorted(d["rows"], key=lambda r: r["slug"])]
    gap = max(r["amount"] for r in d["rows"]) - min(r["amount"] for r in d["rows"])
    return f"""<p>最低賃金は、市区町村ごとには決まっていません。地域別最低賃金は、都道府県ごとに1つずつ定められていて、同じ都道府県の中なら、大阪市でも堺市でも同じ額です。{k.esc(d['label'])}の{k.esc(osaka['name'])}は{k.yen(osaka['amount'])}、{k.esc(sapporo['name'])}は{k.yen(sapporo['amount'])}で、札幌市は北海道の額、大阪市は大阪府の額になります。</p>
<h2>主な市と、適用される最低賃金</h2>
<p>市の名前で探している人が多い市を中心に、その市がある都道府県の額を並べました。</p>
{_t(["市", "都道府県", "最低賃金", "発効日"], trs)}
<h2>47都道府県の主な市</h2>
<p>都道府県ごとに、県庁所在地を含む3つの市(区)を挙げました。ここに載っていない市区町村も、同じ都道府県の中なら、同じ額です。</p>
{_t(["都道府県", "主な市(区)", "最低賃金"], places_rows)}
<h2>どの都道府県の額を使うか</h2>
<ul>
<li><strong>働く場所(事業場)がある都道府県です。</strong>住んでいる都道府県ではありません。隣の県に通勤するときは、勤務先がある県の額です。</li>
<li><strong>派遣で働くときは、派遣先の事業場がある都道府県です。</strong>派遣元の会社がある県は関係ありません(厚生労働省)。</li>
<li><strong>市区町村の違いでは、最低賃金は変わりません。</strong>同じ県の中で通勤先を変えても、最低賃金は同じです。</li>
</ul>
<h2>市で額が変わるように見える場合</h2>
<p>最低賃金は都道府県の額が下限で、実際の時給は求人ごとに違います。都市部の求人の時給が高く見えるのは、最低賃金の差ではなく、求人の条件の違いです。また、地域別最低賃金のほかに、産業ごとの特定(産業別)最低賃金が定められていることがあります。特定(産業別)最低賃金も、都道府県ごとに、産業を決めて定められています。2つ以上の最低賃金が当てはまるときは、最も高い額が適用されます(最低賃金法第6条第1項)。詳しくは<a href="/guide/what-is/">最低賃金とは?仕組みと2つの種類</a>をご覧ください。</p>
<h2>都道府県の間の差</h2>
<p>最低賃金が最も高い都道府県と最も低い都道府県の差は、{k.esc(d['label'])}で{gap}円です。県境を越えて通勤できる範囲では、勤務地の都道府県が変わると、下限の額が変わります。県境の差は、<a href="/analysis/gap/">地域差の分析</a>と、各地方のページ(<a href="/area/kanto/">関東</a>・<a href="/area/kinki/">近畿</a>など)にあります。</p>
"""


BODIES = {"r8": r8_body, "monthly": monthly_body, "city": city_body, "terms": terms_body}
