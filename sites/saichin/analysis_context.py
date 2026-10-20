"""The two sections at the end of each /analysis/ page: "動いた背景" (what the law and the Ministry's publications say about how these numbers come about) and
"あなたにどう関わるか" (what the page's numbers mean for a worker and for an employer).

Everything in the first section is in the Minimum Wage Act (read on e-Gov) or in the Ministry's two press releases of Reiwa 8 (2026-07-28: the guideline, 2026-09-03: the
decisions), both read on 2026-10-20; the sentences that name Reiwa 8 events are written only when the data's last year is Reiwa 8.  No cause of a change in the amounts
is asserted.  The numbers in the second section are computed from the same data as the page.
"""
from __future__ import annotations

from sites.saichin import content
from sites.saichin.analysis import date_series, gap_series, names

VERIFIED = "2026年10月20日"


def _sources(k) -> str:
    items = [content.LAW, content.S_HOW, content.S_MEYASU, content.S_TOSHIN, content.S_FAQ_USER]
    links = "、".join(f'<a href="{u}" rel="noopener" target="_blank">{k.esc(t)}</a>' for t, u in items)
    return f'<p class="notice">この節の出典: {links}。いずれも{VERIFIED}に開いて確かめました。</p>'


def _r8(d: dict) -> bool:
    return d["rows"][0]["history"][-1]["fy"] == 2026


def _section(title: str, parts: list[str]) -> str:
    return f"<h2>{title}</h2>\n" + "\n".join(parts) + "\n"


R8_PROCESS = ("令和8年度は、第75回中央最低賃金審議会が7月28日に、Aランク54円、Bランク56円、Cランク56円の目安を答申しました。目安に関する小委員会で、6回にわたり審議を重ねたうえでの答申です。"
              "目安どおりに上がった場合の全国加重平均は1,176円(+55円、4.9%)で、昨年度の+66円(6.3%)を下回る見込みでした。"
              "9月3日には全都道府県の答申がそろい、全国加重平均は1,177円(+56円)になりました。")


def raises(d: dict, k) -> str:
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    fy = d["rows"][0]["history"][-1]["fy"]
    up = round(avg[fy]) - round(avg[fy - 1])
    process = ("引上げ額は、毎年、次の順で決まります。中央最低賃金審議会が目安を示します。各都道府県の地方最低賃金審議会は、目安を参考に、地域の賃金実態調査や参考人の意見なども踏まえて審議し、答申します。"
               "それを受けて、都道府県労働局長が決定します。" + (R8_PROCESS if _r8(d) else ""))
    law = ("法律は、決めるときに考えることとして、地域の労働者の生計費、労働者の賃金、通常の事業の賃金支払能力を挙げています(最低賃金法第9条)。"
           "生計費は、生活保護の施策との整合性に配慮します。目安には、公益委員見解などの資料が付いていて、厚生労働省のページから見られます。"
           "このサイトでは、その中身は要約していません。上の表や図の増減が、どの事情によるものかは、この分析では言えません。")
    work = (f"<h3>働く人</h3>\n<p>全国加重平均の引上げ額は、{k.esc(d['label'])}が+{up}円です。時給がちょうど最低賃金の人が週20時間・年52週働くと、1年で"
            f"{up}円 × 20時間 × 52週 = {up * 20 * 52:,}円の差になります。自分の時給が、勤務先の県の新しい額以上かどうかは、<a href=\"/check/\">差額チェッカー</a>で確かめられます。</p>")
    boss = ("<h3>雇う人</h3>\n<p>発効日以降は、賃金の計算期間の途中でも、新しい額以上の賃金を払う必要があります(厚生労働省「よくあるご質問」)。県ごとの発効日は<a href=\"/calendar/\">発効日カレンダー</a>にあります。"
            "最低賃金の概要は、見やすい場所に掲示するなどして、労働者に知らせなければなりません(最低賃金法第8条)。引上げに向けた中小企業・小規模事業者への支援策は、厚生労働省の最低賃金制度のサイトで案内されています。</p>")
    return _section("動いた背景(法律と厚生労働省の公表にあること)", [f"<p>{process}</p>", f"<p>{law}</p>", _sources(k)]) + _section("あなたにどう関わるか", [work, boss])


def gap(d: dict, k) -> str:
    g = gap_series(d)
    last, prev = g[-1], g[-2]
    move = "縮まりました" if last["gap"] < prev["gap"] else ("広がりました" if last["gap"] > prev["gap"] else "変わりませんでした")
    ranks = ("国の審議会は、都道府県の経済実態に応じて、全都道府県をA・B・Cの3ランクに分け、ランクごとに引上げ額の目安を示します。現在は、Aランクが6都府県、Bランクが28道府県、Cランクが13県です。"
             + ("令和8年度の目安は、Aランク54円、Bランク56円、Cランク56円で、Aランクの方がB・Cランクより2円小さい額でした(厚生労働省、7月28日)。" if _r8(d) else ""))
    decide = ("目安は参考として示される額で、実際の額は、各地方最低賃金審議会が審議して、都道府県労働局長が決めます。法律は、その地域の労働者の生計費、賃金、通常の事業の賃金支払能力を考えて決めると定めています(最低賃金法第9条)。"
              "このため、同じ年度でも、額は都道府県ごとに別々に決まります。" + ("令和8年度の引上げ額は、+54円から+65円までの幅でした(厚生労働省、9月3日)。" if _r8(d) else ""))
    result = (f"最高額と最低額の差は、{k.esc(prev['label'])}の{prev['gap']}円から、{k.esc(last['label'])}の{last['gap']}円に{move}。")
    hi, lo = k.esc(names(last["hi_rows"])), k.esc(names(last["lo_rows"]))
    work = (f"<h3>働く人</h3>\n<p>{k.esc(last['label'])}の最高額は{hi}の{k.yen(last['max'])}、最低額は{lo}の{k.yen(last['min'])}で、差は{last['gap']}円です。"
            f"1日8時間・年250日働くと、この時給の差は、1年で{last['gap']}円 × 2,000時間 = {last['gap'] * 2000:,}円になります。最低賃金は、住んでいる県ではなく、働く事業場がある県の額で比べます。"
            "派遣で働くときは、派遣先の事業場がある県の額です(厚生労働省)。県境をまたいで通勤する人も、勤務先の県の額です。</p>")
    boss = ("<h3>雇う人</h3>\n<p>法律上の下限は、事業場がある県の額です。複数の県に事業場があるときは、事業場ごとに、その県の額が下限になります。"
            "県境の近くで人を募集するときは、隣の県の額も、時給を決めるときの参考になります。県ごとの額は<a href=\"/\">全国の一覧</a>で見られます。</p>")
    return _section("動いた背景(法律と厚生労働省の公表にあること)", [f"<p>{ranks}</p>", f"<p>{decide}{result}</p>", _sources(k)]) + _section("あなたにどう関わるか", [work, boss])


def milestones(d: dict, k) -> str:
    ys = d["long_years"]
    first1000 = next(y for y in ys if y["avg"] is not None and y["avg"] >= 1000)
    amounts = [r["amount"] for r in d["rows"]]
    n = {t: sum(1 for a in amounts if a > t) for t in (1000, 1100, 1200)}
    law = ("1,000円、1,100円、1,200円という区切りは、法律にも、審議会の目安にも、定められていません。読みやすい節目として、このサイトが選んだものです。"
           f"全国加重平均が初めて1,000円以上になったのは、{k.esc(first1000['label'])}です。法律が定めているのは、地域別最低賃金を時間額で決めること(第3条)と、"
           "生計費・賃金・通常の事業の賃金支払能力を考えること(第9条)です。決定の手続は、次のとおりです。審議会の意見を聴きます(第10条)。意見の要旨を公示し、公示の日から15日以内の異議の申出を受けます(第11条)。"
           "決定を公示すると、公示の日から30日を過ぎた日に効力が生じます(第14条第2項)。" + ("令和8年度は、7月28日に目安が示され、9月3日に全都道府県の答申がそろいました。全国加重平均は1,177円です。" if _r8(d) else ""))
    work = (f"<h3>働く人</h3>\n<p>{k.esc(d['label'])}は、最低賃金が1,000円を超える都道府県が{n[1000]}、1,100円を超える都道府県が{n[1100]}、1,200円を超える都道府県が{n[1200]}です。"
            f"時給1,100円の求人は、最低賃金が1,100円を超える{n[1100]}都道府県では、最低賃金を下回ります。求人の時給は、勤務先の県の額と、発効日の日付で確かめてください。"
            "手当や残業代を除いた時給で比べる方法は、<a href=\"/guide/excluded/\">最低賃金に含まれない賃金は?</a>にあります。</p>")
    boss = ("<h3>雇う人</h3>\n<p>最低賃金が上がった県では、新しい額が、発効日からの下限になります。求人票、シフト表、給与システムの時給が、新しい額を下回っていないか、発効日までに確かめます。"
            "月給の求人は、1か月の平均の所定労働時間で割って、時間額に直してから比べます。早見表は<a href=\"/guide/monthly/\">最低賃金の月給換算</a>にあります。</p>")
    return _section("動いた背景(法律と厚生労働省の公表にあること)", [f"<p>{law}</p>", _sources(k)]) + _section("あなたにどう関わるか", [work, boss])


def ranks(d: dict, k) -> str:
    moves = []
    for r in d["rows"]:
        a, b = r["long"][-2], r["long"][-1]
        if a["rank"] is not None and b["rank"] is not None:
            moves.append((a["rank"] - b["rank"], r, a, b))
    up = max(m[0] for m in moves)
    down = min(m[0] for m in moves)
    ups = [m for m in moves if m[0] == up]
    downs = [m for m in moves if m[0] == down]

    def who(ms) -> str:
        return "、".join(f"{k.esc(m[1]['name'])}({m[2]['rank']}位から{m[3]['rank']}位)" for m in ms[:3]) + ("など" if len(ms) > 3 else "")
    last_label = k.esc(moves[0][3]["label"])
    basis = ("順位は、47都道府県の額を比べた結果です。自分の県が同じ額を引き上げても、ほかの県がそれ以上引き上げれば、順位は下がります。引上げ額は、都道府県ごとに別々に決まります。"
             "目安は参考として示される額で、地方最低賃金審議会は、地域の賃金実態調査や参考人の意見なども踏まえて審議します(厚生労働省、7月28日)。"
             + ("令和8年度の目安は、Aランク54円、Bランク56円、Cランク56円でしたが、決まった引上げ額は+54円から+65円までの幅でした(厚生労働省、9月3日)。" if _r8(d) else ""))
    result = (f"{last_label}に順位が最も上がったのは{who(ups)}、最も下がったのは{who(downs)}です。")
    top = max(d["rows"], key=lambda r: (r["raise"], r["name"]))
    work = (f"<h3>働く人</h3>\n<p>順位が上がっても、あなたの時給が自動で上がるわけではありません。逆に、順位が下がっても、県の額が上がれば、下限は上がります。確かめるのは、勤務先の県の最低賃金の額と発効日です。"
            f"たとえば{k.esc(top['name'])}の最低賃金は、{k.yen(top['prev_amount'])}から{k.yen(top['amount'])}(+{top['raise']}円)になりました。時給がちょうど最低賃金の人が週20時間・年52週働くと、"
            f"1年の収入は{top['raise']}円 × 20時間 × 52週 = {top['raise'] * 20 * 52:,}円増えます。</p>")
    boss = ("<h3>雇う人</h3>\n<p>近くの県より順位が低くても、守る下限は、自分の事業場がある県の額です。県の額が上がったときは、発効日以降の賃金が、新しい額を下回っていないか確かめます。"
            "賃金の計算期間の途中で発効日が来る場合も、発効日以降の分は新しい額です(厚生労働省「よくあるご質問」)。</p>")
    return _section("動いた背景(法律と厚生労働省の公表にあること)", [f"<p>{basis}{result}</p>", _sources(k)]) + _section("あなたにどう関わるか", [work, boss])


def dates(d: dict, k) -> str:
    ds = [s for s in date_series(d) if s["n"]]
    last = ds[-1]
    law = ("発効日は、法律の手続で決まります。審議会の意見の要旨が公示されると、その地域の労働者や使用者は、公示の日から15日以内に異議を申し出られます。15日が過ぎるまでは、決定できません(最低賃金法第11条)。"
           "決定が公示されると、公示の日から30日を過ぎた日に効力が生じます。決定で、それより後の日を定めることもできます(第14条第2項)。"
           "答申や公示の日は都道府県ごとに違うため、発効日も都道府県ごとに違います。"
           + ("令和8年度は、10月1日から12月2日までの間に、都道府県ごとに順次発効します(厚生労働省、9月3日)。" if _r8(d) else ""))
    work = (f"<h3>働く人</h3>\n<p>発効日の前の分は、改定前の額と比べます。発効日以降の分は、賃金の計算期間の途中でも、新しい額以上でなければなりません(厚生労働省「よくあるご質問」)。"
            f"{k.esc(d['label'])}で最も遅いのは{k.esc(names(last['last_rows']))}の{k.jp_date(last['last'].isoformat())}で、それより前の勤務分は、改定前の額で比べます。"
            f"最も早い{k.jp_date(last['first'].isoformat())}の都道府県との間に、{last['span']}日の開きがあります。自分の県の日付は<a href=\"/calendar/\">発効日カレンダー</a>で調べられます。</p>")
    boss = ("<h3>雇う人</h3>\n<p>発効日に合わせて、時給、シフト、給与システムの設定を見直します。事業場が複数の県にあるときは、県ごとに発効日が違います。"
            "最低賃金の概要は、見やすい場所に掲示するなどして、労働者に知らせなければなりません(最低賃金法第8条)。</p>")
    return _section("動いた背景(法律と厚生労働省の公表にあること)", [f"<p>{law}</p>", _sources(k)]) + _section("あなたにどう関わるか", [work, boss])


SECTIONS = {"gap": gap, "milestones": milestones, "ranks": ranks, "raises": raises, "dates": dates}
