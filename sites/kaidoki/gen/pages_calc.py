"""The calculator page, the point-rate page and the cap table.  The formulas are the ones in assets/calc.js; tests/test_kaidoki.py runs both and compares."""
from __future__ import annotations

from math import ceil, floor

from .kit import R, S, T, page


def real_price(price, ship=0, coupon=0, rate=0, cap=0, excl_tax=True, use=100):
    """Same as compute() in assets/calc.js."""
    coupon = min(coupon, price)
    after = price - coupon
    base = after / 1.1 if excl_tax else after
    pts = floor(base * rate / 100)
    if cap > 0:
        pts = min(pts, cap)
    usable = floor(pts * use / 100)
    pay = after + ship
    return {"pay": pay, "points": pts, "usable": usable, "real": pay - usable}


def n(x) -> str:
    return f"{x:,}"


def cap_rows(cap=7000):
    """Marathon: n shops -> n times, the 1 times of the usual points is not part of the bonus, so the bonus is (n-1)%.  Tax-excluded total at which the cap is reached."""
    rows = []
    for shops in range(2, 11):
        bonus = shops - 1
        reach = ceil(cap * 100 / bonus)
        per = ceil(reach / shops)
        rows.append([f"{shops}ショップ", f"{shops}倍", f"{bonus}%", f"{n(reach)}円", f"{n(per)}円"])
    return rows


def calc_form() -> str:
    def col(label: str, d: dict) -> str:
        return f'''<div class="calc-col"><h3>{label}</h3>
<label>商品の価格(税込・円)<input type="text" inputmode="numeric" name="price" value="{d.get('price','')}" autocomplete="off"></label>
<label>送料(円。無料なら0)<input type="text" inputmode="numeric" name="ship" value="{d.get('ship','0')}" autocomplete="off"></label>
<label>クーポンの値引き(円)<input type="text" inputmode="numeric" name="coupon" value="{d.get('coupon','0')}" autocomplete="off"></label>
<label>付くポイントの合計(%。例: 通常1%と上乗せ9%なら10)<input type="text" inputmode="decimal" name="rate" value="{d.get('rate','1')}" autocomplete="off"></label>
<label>ポイントの上限(ポイント。上限が無ければ空欄)<input type="text" inputmode="numeric" name="cap" value="" autocomplete="off"></label>
<label>付いたポイントのうち、使い切る割合(%)<input type="text" inputmode="numeric" name="use" value="100" autocomplete="off"></label>
<label class="chk"><input type="checkbox" name="excl_tax" checked> ポイントは、税抜の金額に対して付く</label>
<div class="calc-out" aria-live="polite"></div></div>'''
    return ('<div class="calc">' + col("案A", {"price": "11000", "ship": "500", "coupon": "1000", "rate": "10"}) +
            col("案B(使わなければ空のまま)", {"ship": "0", "coupon": "0", "rate": "1"}) + '</div>\n<script src="/assets/calc.js" defer></script>')


def pages() -> list[dict]:
    ex = real_price(11000, 500, 1000, 10)
    ex2 = real_price(11000, 500, 1000, 1)
    rows = cap_rows()
    calc = page(
        "/calc/", "hub", "/", "楽天ポイント倍率計算", "楽天ポイント倍率計算と実質価格の出し方(税抜・クーポン後)",
        "楽天ポイント倍率計算と実質価格のツール",
        "価格、送料、クーポン、ポイント倍率を自分で入れると、実質価格が出ます。ポイントが税抜・クーポン後に付く点や、使い切れないポイントも計算に入れられ、2つの案を並べて見られます。",
        "実質価格は、支払う金額から、使い切れるポイントを引いた額です。下の欄に数字を入れると、案Aと案Bを並べて計算します。",
        [
            S("数字を入れて計算する", "入れた数字はこのページの中だけで計算します。送信も保存もしません。2つの案を並べて見られますが、どちらが良いかの判定は出しません。判断は、出てきた数字を見て自分で決めてください。", html=calc_form()),
            S("計算の式", f"実質価格は、(商品の価格 − クーポン + 送料)から、使い切るポイントを引いた額です。付くポイントは、(商品の価格 − クーポン)に倍率をかけて、小数点以下を切り捨てます。税抜に付く場合は、先に1.1で割ります。",
              f"最初から入っている案Aの数字で計算すると、支払う金額は{n(ex['pay'])}円、付くポイントは{n(ex['points'])}ポイントで、実質価格は{n(ex['real'])}円です。同じ条件でポイントが通常の1%だけなら、付くポイントは{n(ex2['points'])}ポイント、実質価格は{n(ex2['real'])}円になります。差は{n(ex2['real']-ex['real'])}円です。"),
            S("入れる前に確かめる3点", "ポイントは、クーポンを引いたあとの金額に付くのが一般的です。楽天市場のお買い物マラソンも、税抜・送料別・クーポン適用後の金額に付くと案内されています。送料にはポイントが付かないので、送料の高い店は、倍率が高くても実質価格が下がらないことがあります。",
              "期間限定ポイントは、期限までに使い切れないと価値が下がります。使い切る割合の欄を、自分が使う見込みに合わせて下げてください。ポイントの上限がある企画では、上限の欄に数字を入れると、上限で止まる分まで計算します。"),
            S("買いまわりの上限に届く金額の目安", f"お買い物マラソンの買いまわりは、ショップ数が増えるほど倍率が上がり、特典ポイントの上限は7,000ポイントです。通常の1倍分は上乗せに含まれないので、2ショップなら上乗せは1%、10ショップなら9%です。上乗せ分が上限に届く、税抜の合計金額を下の表にしました。",
              table=T("買いまわりの上限7,000ポイントに届く、税抜の合計金額", ["購入ショップ数", "倍率", "上乗せ分", "上限に届く税抜の合計", "1ショップあたり"], rows, [1, 2, 3, 4],
                      "ショップ数で決まる倍率が期間中の買い物すべてに付くと考えた目安です。実際の付与は主催者の案内に従います。")),
        ],
        [R("/calc/points/", "ポイント倍率の計算の考え方"), R("/rakuten/marathon-cap/", "お買い物マラソンの上限と攻略"), R("/what-to-buy/", "セールで買うもの・見送るもの"), R("/calendar/", "セール日程の一覧")],
        intent=5, secondary=["楽天 ポイント 倍率 計算", "実質価格 計算"], basis="楽天の買いまわりの案内(2026年11月)",
    )
    pts = page(
        "/calc/points/", "article", "/calc/", "ポイント倍率の計算", "ポイント倍率の計算のしかた(税抜・上限・使い切る割合)",
        "ポイント倍率の計算のしかたと、実質価格の落とし穴",
        "ポイント倍率で本当に何円得になるかを、税抜・クーポン後・上限・期限の4点から計算する考え方です。倍率の違いによる実質価格の例を表にしました。",
        "倍率の数字より、何円に対して付くのかと、上限と期限が先です。例題の表で、同じ倍率でも実質価格が変わる理由を確かめられます。",
        [
            S("倍率は、何円にかけるのか", "「ポイント10倍」という言葉は、支払う金額に10%が付くという意味ではありません。通常の1倍(1%)を含む場合と、含まない場合があります。さらに、かける相手の金額が、税込か税抜か、クーポンを引く前か後かで変わります。",
              "楽天市場のお買い物マラソンでは、特典ポイントは、通常の1倍を除いた倍率で、税抜・送料別・クーポン適用後の金額に付くと案内されています。倍率の表示を見たら、まず「通常の分を含むか」「何円にかけるか」の2点を探します。"),
            S("同じ倍率でも、実質価格は変わる", "次の表は、11,000円(税込)の品を、送料500円、クーポン1,000円で買う3つの場合です。ポイントは税抜に付き、すべて使い切るとして、このサイトの計算ツールと同じ式で出しました。",
              table=T("11,000円の品の実質価格(送料500円・クーポン1,000円・税抜に付与)", ["ポイントの合計", "支払う金額", "付くポイント", "実質価格", "実質の値引き率"],
                      [[f"{r}%", f"{n(v['pay'])}円", f"{n(v['points'])}ポイント", f"{n(v['real'])}円", f"{(11000+500-v['real'])/(11000+500)*100:.1f}%"]
                       for r in (1, 5, 10, 20) for v in [real_price(11000, 500, 1000, r)]], [1, 2, 3, 4])),
            S("上限があると、倍率が効かなくなる", "ポイントの上限がある企画は、金額が大きくなるほど、倍率の効き目が薄まります。買いまわりの特典なら、上限は7,000ポイントです。上乗せ9%の場合、税抜77,778円で上限に届きます。それ以上の買い物には、同じ企画からはポイントが付きません。",
              "10万円の家電を1点買う場合と、1万円の品を10ショップで買う場合では、倍率の働き方が違います。後者は倍率が上がりますが、1ショップ1,000円以上の条件を満たし続ける必要があります。"),
            S("使い切れないポイントは、実質価格に入れない", "期間限定ポイントは、期限までに使い切れないと意味がありません。使う予定のない分まで実質価格から引くと、実際より安く見えます。計算ツールの「使い切る割合」を、日用品の買い足しで確実に使える範囲に下げて、実質価格を見直してください。",
              "送料も同じです。送料は、ポイントの対象外であることが多いので、本体価格が安くても送料込みでは高くなる場合があります。比べるときは、必ず送料を足した額で見ます。"),
        ],
        [R("/calc/", "実質価格の計算ツール"), R("/rakuten/marathon-cap/", "お買い物マラソンの上限と攻略"), R("/rakuten/marathon/", "お買い物マラソンはいつ")],
        intent=5, secondary=["実質価格 計算"], basis="楽天の買いまわりの案内(2026年11月)",
    )
    return [calc, pts]
