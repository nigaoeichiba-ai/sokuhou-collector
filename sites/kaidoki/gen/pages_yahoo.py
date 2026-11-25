"""/yahoo/black-friday/: how to put the purchases together during the Yahoo!ショッピング ブラックフライデー 2026 (the condition is the total amount, not the number of shops).
The conditions were read on the organiser's campaign page on CHECKED_BF (INTERNAL: shopping.yahoo.co.jp/promotion/campaign/blackfriday/ 「ブラックフライデー詳細」and the お得ガイド); the amounts in the examples are computed here.
After the end the page speaks in the past."""
from __future__ import annotations

from html import escape

from .common import TODAY, ev_span, jp, phase, until
from .facts import BY_ID
from .kit import R, S, page

CHECKED_BF = "2026-11-25"
LOW, HIGH = 5000, 20000            # the totals (coupons taken off, shipping and fees added) that open the two rates
RATE_LOW, RATE_HIGH = 4, 7
CAP = 7000                         # points per person for the whole period
GRANT = "2026-12-25"               # the earliest day the points are given
TAX = 10
BF_URL = "https://shopping.yahoo.co.jp/promotion/campaign/blackfriday/"
BONUS_URL = "https://shopping.yahoo.co.jp/promotion/campaign/bsplus/"
GUIDE_URL = "https://shopping.yahoo.co.jp/promotion/campaign/guide/"


def points(goods_incl: int, shipping: int = 0) -> tuple[int, int, int]:
    """(rate, the amount the points are counted on, the points) for goods at 10% tax: the total with shipping picks the rate, the points are counted on the goods without tax."""
    total = goods_incl + shipping
    rate = RATE_HIGH if total >= HIGH else RATE_LOW if total >= LOW else 0
    base = goods_incl * 100 // (100 + TAX)
    return rate, base if rate else 0, min(base * rate // 100, CAP)


def cap_amount() -> int:
    """The goods amount without tax at which the cap is reached with the higher rate."""
    return -(-CAP * 100 // RATE_HIGH)


def yen(n: int) -> str:
    return f"{n:,}円"


def link(url: str, label: str) -> str:
    from sites.kaidoki.redesign import affiliate as AFF
    return AFF.lines(AFF.product_links({"slug": "", "crumb": ""}, {"aff": [{"k": "vc", "key": "yahoo", "url": url, "label": label}], "name": ""}))


def items(rows: list) -> str:
    """A list instead of a table: on a phone the second and third columns of a table would be off the screen."""
    return "<ul>" + "".join(f"<li><strong>{escape(k)}</strong>: {escape(v)}</li>" for k, v in rows) + "</ul>"


def example_rows() -> list[list[str]]:
    out = []
    for goods, ship in ((4400, 0), (4400, 700), (11000, 0), (19800, 0), (22000, 0), (110000, 0)):
        rate, base, pt = points(goods, ship)
        out.append([yen(goods) + (f"と送料{yen(ship)}" if ship else ""), f"+{rate}%" if rate else "対象外", f"{pt:,}ポイント"])
    return out


def example_table() -> str:
    """Two columns that fit a phone (the site's tables are 560px wide by default, which would hide the points)."""
    body = "".join(f"<tr><th scope=\"row\">{escape(a)}</th><td>{escape(c)}({escape(b)})</td></tr>" for a, b, c in example_rows())
    return ('<div class="tablewrap"><table style="min-width:0;width:100%"><caption>合計金額とポイントの例</caption><thead><tr><th scope="col">買う金額(税込)</th><th scope="col">付くポイント(率)</th></tr></thead><tbody>'
            + body + "</tbody></table></div>")


def pages() -> list[dict]:
    ev = BY_ID["ybf-2026"]
    done = phase(ev) == "done"
    span = ev_span(ev)
    short_rate = points(19800)[2]
    long_rate = points(22000)[2]
    cap = cap_amount()
    cap_incl = cap * (100 + TAX) // 100

    if not done:
        title = "ヤフーショッピング買い回り|ブラックフライデー2026の合計金額の条件と上限"
        h1 = "ヤフーショッピング買い回りの組み立て(ブラックフライデー2026)"
        desc = f"Yahoo!ショッピングのブラックフライデー2026は、合計金額に応じて+{RATE_LOW}%か+{RATE_HIGH}%のポイントが付きます。エントリー、対象商品、合計の数え方と上限を、買う順番に沿ってまとめました。"
        lead = f"条件は店の数ではなく合計金額です。エントリーして対象商品を買い、合計金額が条件に届くと+{RATE_LOW}%か+{RATE_HIGH}%のポイントが付きます。"
    else:
        title = "ヤフーショッピング買い回り|ブラックフライデー2026の条件の記録(終了)"
        h1 = "ヤフーショッピング買い回りの記録(ブラックフライデー2026は終了)"
        desc = f"Yahoo!ショッピングのブラックフライデー2026は終了しました。合計金額で率が変わる条件、対象の数え方、上限を記録として残し、次の大型セールの日程へ案内します。"
        lead = f"ブラックフライデー2026は終了しました。条件は店の数ではなく合計金額で、金額に応じて+{RATE_LOW}%か+{RATE_HIGH}%のポイントでした。"
    be = "でした" if done else "です"

    cond = items([
        ["期間", span],
        ["エントリー", "必要。期間中に1回で、買い物のあとでも期間内なら対象"],
        ["対象の商品", "BONUSの目印が付いた商品(一部は対象外)"],
        ["合計の数え方", "クーポンを引いた金額に、送料と手数料を足した額。複数の注文を合算できる"],
        ["率", f"{yen(LOW)}から{yen(HIGH - 1)}は+{RATE_LOW}%、{yen(HIGH)}以上は+{RATE_HIGH}%"],
        ["ポイントの対象額", "税抜の商品代からクーポンなどを引いた額。送料と手数料は入らない"],
        ["上限", f"期間中に1人{CAP:,}円相当"],
        ["付与", f"最短で{jp(GRANT)}。利用先と期間が限られるPayPayポイント"],
    ])
    cond = f"<p>{escape(jp(CHECKED_BF))}に確認した、ブラックフライデー2026の条件です。</p>" + cond

    secs = [
        S("条件は合計金額で決まる", f"楽天の買いまわりは買った店の数で倍率が上がりますが、Yahoo!ショッピングのこの企画は、対象商品の合計金額で率が決まり{'ました' if done else 'ます'}。同じIDでの複数の注文は合算されるので、別々の店で分けて買っても合計に入り{'ました' if done else 'ます'}。",
          html=cond),
        S("組み立ての順番" if not done else "組み立ての考え方",
          f"最初にエントリーをします。次に、期限があって買う予定の物を書き出し、BONUSの目印が付いているかを商品ごとに調べます。対象外の商品が同じ注文に入ると、その注文の対象商品まで外れるので、対象外の物は注文を分けるのが安全{be}。",
          f"そのうえで合計を出します。{yen(HIGH)}に届くかどうかで率が変わります。届かない分を埋めるために要らない物を足すと、ポイントより支払いが増えます。足すのは、近いうちに必ず使う日用品などに限ります。" if not done else f"合計が{yen(HIGH)}に届くかどうかで率が変わりました。届かない分を埋めるために要らない物を足すと、ポイントより支払いが増えます。次の機会も同じ考え方が使えます。",
          html=link(BF_URL, "Yahoo!ショッピングのブラックフライデーのページでエントリーする" if not done else "Yahoo!ショッピングのブラックフライデーのページを見る")),
        S("金額ごとの付くポイント", f"消費税{TAX}%の商品を、クーポンを使わずに買った場合の計算です。合計には送料が入り、ポイントは税抜の商品代に付きます。食品は税率が違うので、数字が少し変わります。",
          f"税込19,800円なら{short_rate:,}ポイント、税込22,000円なら{long_rate:,}ポイントです。{yen(HIGH)}の手前にいるときは、少し足すと率が上がります。",
          html=example_table()),
        S("上限に届く金額", f"+{RATE_HIGH}%で上限の{CAP:,}円相当に届くのは、税抜でおよそ{yen(cap)}、税込でおよそ{yen(cap_incl)}分の買い物{be}。これを超える分には、この企画のポイントは付き{'ませんでした' if done else 'ません'}。高い物を複数買う予定なら、上限を超える分は別のセールに回す手もあります。"),
        S("ほかの特典と重ねるとき", f"ブラックフライデーの期間には、対象のストアで買うボーナスストアPlus(+4%または+9%、さらに+2%の企画)や、指定の支払い方法の企画(最大+5%、上限は月5,000円相当)も案内されてい{'ました' if done else 'ます'}。それぞれ条件と上限が別です。ボーナスストアPlusは、エントリーのあとの注文が対象なので、順番に気をつけます。",
          f"ボーナスストアPlusの対象ストアは、日によって入れ替わることがあります。注文前に、商品ページやカートの内訳に出る率を読んでおきましょう。11月25日の5のつく日は、ブラックフライデーのため開催がありません。",
          html=link(BONUS_URL, "Yahoo!ショッピングのボーナスストアPlusの対象を見る")),
        S("よくある疑問",
          f"Q. 何店舗で買えば特典が増えるか。A. この企画の条件に店の数はなく、合計金額で決まり{'ました' if done else 'ます'}。",
          f"Q. 送料は合計に入るか。A. {yen(LOW)}と{yen(HIGH)}の判定には入ります。ポイントを計算する金額には入りません。",
          "Q. ポイントはいつ使えるか。A. 最短で12月25日に付き、使える場所と期間が限られます。値引きと同じには数えず、使う予定を考えておきます。"),
    ]
    if done:
        secs.append(S("次の大型セール", "ブラックフライデーのあとの日程は、Yahoo!ショッピングのセールのページとセール日程の一覧にまとめています。", html=link(GUIDE_URL, "Yahoo!ショッピングのお得ガイドを見る")))
    p = page(
        "/yahoo/black-friday/", "article", "/yahoo/", "ヤフーショッピング 買い回り", title, h1, desc, lead, secs,
        [R("/yahoo/", "Yahoo!ショッピングのセール日程"), R("/black-friday/", "ブラックフライデーのモール別日程"), R("/calc/", "実質価格の計算ツール"), R("/calendar/", "セール日程の一覧")],
        intent=1, secondary=["ヤフーショッピング 買い回り いつ", "ヤフーブラックフライデー 上限"], basis=f"LINEヤフーの案内({jp(CHECKED_BF)}確認)",
    )
    return [p]
