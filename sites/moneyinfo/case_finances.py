"""Editable assumptions and verified rates. Source URLs stay outside the generated site."""
from decimal import Decimal
from html import escape

CHECKED = "2026-11-18"
SOURCES = {
    "rail": "https://ekitan.com/transit/article/shinkansen/section/sf-2590_st-5198",
    "stay": "https://yh-kyoto.or.jp/utano_yh/location",
    "stay_tax": "https://www.city.kyoto.lg.jp/gyozai/page/0000236942.html",
    "kyoto_bus": "https://www.city.kyoto.lg.jp/kotsu/page/0000240682.html",
    "reserved": "https://smart-ex.jp/product/plan/service/pdf/service-reserve_price.pdf",
    "deli": "https://www.sej.co.jp/products/a/item/102550/",
    "cook": "https://www.topvalu.net/items/list/100150400/",
    "kit": "https://www.oisix.com/shop.kounyuu--oic_intro_shinki_ryoukin__html.htm",
    "deli_delivery": "https://www.oisix.com/ShouhinShousai.ss8-9836.o.htm",
    "deli_shipping": "https://www.oisix.com/shop.g6--guide--guide_shipping-fee__html.htm",
    "deli_frozen": "https://faq.oisix.com/inquiries/f3606debb8884f52dd47?select_sid=7997941",
    "dinner_rice": "https://www.topvalu.net/items/detail/4549414698855/",
    "dinner_side": "https://www.topvalu.net/items/detail/4549414704662/",
    "dinner_soup": "https://www.topvalu.net/items/list/100625300/?brand=2&direction=desc&page=3&sort=Products.release_datetime",
    "rental": "https://www.kasite.com/products/detail/22",
    "purchase": "https://www.nitorihd.co.jp/news/items/3e3e37c65c48c700539755aa0e66cdaa.pdf",
    "rental_setup": "https://www.kasite.com/rental_info/detail/5472",
    "rental_area": "https://www.kasite.com/area/tokyo",
    "recycle": "https://www.rkc.aeha.or.jp/recycle_price/2441.php",
    "recycle_dropoff": "https://www.city.shinjuku.lg.jp/seikatsu/file09_01_00019.html",
    "purchase_delivered": "https://www.ksdenki.com/shop/g/g4582678513502/",
    "purchase_pickup": "https://www.ksdenki.com/guide/delivery_recycle",
    "purchase_recycle": "https://aqua-has.com/about/recycle/",
    "tourism": "https://www.e-stat.go.jp/stat-search/file-download?fileKind=0&statInfId=000040450817",
    "stamp": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/inshi/7108.htm",
    "brokerage": "https://www.mlit.go.jp/totikensangyo/const/1_6_bf_000013.html",
}

def yen(n):
    return f"{n:,}円"


RAIL = (13320 * 2 + 6660) * 2
STAY = 4200 * 2 + 3550 + 200 * 3
BUS = (230 * 2 + 120) * 2
TOGETHER = RAIL + STAY + BUS
RESERVED = (13970 * 2 + 6980) * 2
RESERVED_TRIP = RESERVED + STAY + BUS
RENT_USED, RENT_NEW, BUY = 13750, 26400, 24900
RECYCLE = 3300
BUY_COMPARABLE, BUY_SETUP = 43780, 3850
BUY_RECYCLE, BUY_TRANSPORT, BUY_VISIT = 2574, 2750, 3300
BUY_ALL = BUY_COMPARABLE + BUY_SETUP + BUY_RECYCLE + BUY_TRANSPORT + BUY_VISIT
STAMP, BROKERAGE_LIMIT, DOWN_PAYMENT = 10000, 1386000, 2000000
HOUSE_KNOWN = STAMP + BROKERAGE_LIMIT + DOWN_PAYMENT
TRAVEL_OVERNIGHT, TRAVEL_DAY = 51042, 18670
DELI_TWO = Decimal("537.84") * 2
COOK_TWO = Decimal("537.84")
DELI_DELIVERY, SMALL_ORDER_SHIPPING, FROZEN_FEE = 678, 1200, 300
RICE_TWO = Decimal("159.84") * 2
SIDE_TWO = Decimal("149.04")
SOUP_TWO = Decimal("213.84") / 12 * 2
DINNER_COMMON = RICE_TWO + SIDE_TWO + SOUP_TWO
DINNER_DELI = DINNER_COMMON + DELI_TWO
DINNER_COOK = DINNER_COMMON + COOK_TWO
DINNER_DELIVERY = DINNER_COMMON + DELI_DELIVERY + SMALL_ORDER_SHIPPING

# Values in yen. Monthly gross and annual gross are distinct, with bonuses separate.
# Monthly deductions are assumed inputs, not a tax or social insurance simulation.
PROFILES = {
    "case-family-trip": {
        "people": (("本人・法人営業（正社員）", 300000, 400000, 240000),
                   ("配偶者・経理事務（正社員）", 250000, 300000, 200000)),
        "out": (("住居", 110000), ("食費・日用品", 85000), ("水道光熱・通信", 35000),
                ("教育・保育", 50000), ("交通・保険", 35000), ("その他", 45000)),
        "side": 0, "saving": 40000, "invest": 20000, "cash": 2200000, "assets": 450000,
        "action": f"往復、宿泊、宿までのバス代の{yen(TOGETHER)}を4回で準備するには毎月{yen((TOGETHER + 3) // 4)}必要です。通常月に残る2万円を超えるため、食事などの予算も加えたうえで、準備期間を延ばす案や実家に泊まる案を考えます。",
        "options": "交通と宿泊の予約は、家族全員の取消条件と支払日までそろえて比較しましょう。宿に泊まらず実家へ帰る場合も別案として残します。",
    },
    "case-weeknight-dinner": {
        "people": (("本人・システム運用（正社員）", 340000, 500000, 270000),
                   ("配偶者・営業事務（正社員）", 260000, 300000, 210000)),
        "out": (("住居", 135000), ("食費・日用品", 95000), ("水道光熱・通信", 35000),
                ("通勤・外出", 25000), ("保険・医療", 25000), ("その他", 55000)),
        "side": 10000, "side_label": "資料校正の副業。手数料等を引いた後の仮定", "saving": 45000, "invest": 25000, "cash": 2600000, "assets": 700000,
        "action": "このさばの例で作り置きから惣菜へ月4回替えると、主なおかず代だけで約2,151円増えます。食費全体を見直す前に夕食だけを記録し、宅配も送料を含む通常月の差額で判断します。副収入が入らない月は家計に残る額が1万円減るため、継続注文の費用は給与の範囲でも払えるか考えます。",
        "options": "食材宅配を試すのは、受取日と調理時間を確保できる週に。帰宅後に温めるだけの日が必要なら、惣菜のほうが予定に合います。",
    },
    "case-temporary-appliances": {
        "people": (("本人・設備保守（正社員）", 330000, 500000, 260000),
                   ("配偶者・販売（パート）", 110000, 0, 100000)),
        "out": (("住居", 95000), ("食費・日用品", 75000), ("水道光熱・通信", 30000),
                ("交通・保険", 40000), ("その他", 55000)),
        "side": 0, "saving": 30000, "invest": 15000, "cash": 1600000, "assets": 300000,
        "action": "表の支出は赴任前の家計です。赴任用の費用は別に置き、会社が後で精算する場合も、立て替える月に現金を用意します。通常月の残り2万円から中古レンタルの例13,750円を出すと、残りは6,250円です。通常の配送・設置・回収が含まれる例でも、時間指定などのオプションと精算月は別に書きます。",
        "options": "洗濯機だけ必要なら期間型の単品を比較します。冷蔵庫なども必要ならセットの総額を調べ、備え付けの品と重複がないかを最初に確認しましょう。",
    },
    "article": {
        "people": (("本人・機械設計（正社員）", 360000, 700000, 285000),
                   ("配偶者・人事事務（正社員）", 290000, 400000, 230000)),
        "out": (("住居", 125000), ("食費・日用品", 90000), ("水道光熱・通信", 35000),
                ("教育・保育", 45000), ("交通・保険", 45000), ("その他", 55000)),
        "side": 0, "saving": 65000, "invest": 25000, "cash": 6000000, "assets": 850000,
        "action": "確認済みの費目を支払っても、手元の現金を全部使えるわけではありません。たとえば残った現金260万4,000円から、生活用に残す額と引越し・登記・保険などの見積もりを引きます。毎月残る3万円だけで追加費用を用意するなら、支払日までの月数も確認します。",
        "options": "借入額や毎月の返済を調べる際は、費用を項目別に示す見積もりを比べましょう。資金計画を相談する場合も、相談後の契約条件や費用を確認します。",
    },
}


def profile_html(slug):
    p = PROFILES[slug]
    income = sum(x[3] for x in p["people"]) + p["side"]
    gross = sum(x[1] * 12 + x[2] for x in p["people"])
    spending = sum(x[1] for x in p["out"])
    balance = income - spending - p["saving"] - p["invest"]
    rows = [(name, f"月収 {yen(month)}（額面）／通常月の手取り {yen(net)}／年収 {yen(month * 12 + bonus)}（額面・賞与 {yen(bonus)}を含む）")
            for name, month, bonus, net in p["people"]]
    rows += [
        ("世帯の給与年収", f"{yen(gross)}（額面）"),
        ("世帯の通常月の収入", f"{yen(income)}（手取りと副収入の計）"),
        ("副収入", f"{yen(p['side'])}（{p['side_label']}）" if p.get("side_label") else yen(p["side"])),
        *p["out"],
        ("返済中の借入", "なし（住宅購入後の借入は別）" if slug == "article" else "なし"),
        ("毎月の生活費 合計", yen(spending)),
        ("毎月の貯金／投資への積立", f"{yen(p['saving'])}／{yen(p['invest'])}"),
        ("現在の預貯金／投資資産", f"{yen(p['cash'])}／{yen(p['assets'])}"),
    ]
    items = "".join(f"<dt>{escape(label)}</dt><dd>{escape(value if isinstance(value,str) else yen(value))}</dd>"
                    for label,value in rows)
    return f'''<section class="guide-section household-profile" id="household-profile">
<h2>この世帯の家計と見直せるところ</h2>
<p>職種、収入、生活費、資産はモデルケースの仮定です。職種の平均や給与の実績を表すものではありません。この数字で通常月の収支を試算しました。本文の料金例は調べた掲載価格です。</p>
<dl>{items}</dl>
<h3>生活費と積立を引いた後に残る額</h3>
<p>通常月は {yen(income)} − {yen(spending)} − {yen(p["saving"])} − {yen(p["invest"])} で、残りは <strong>{yen(balance)}</strong>です。年払い、臨時支出、今回の費用をここから見込みます。</p>
<p>{escape(p["action"])}</p>
<h3>サービスを選ぶ前に確認すること</h3><p>{escape(p["options"])}</p>
<p>支払日が決まっている資金は、毎月の投資積立や値動きのある資産と別に把握します。<a href="basics-savings.html">お金を使う時期と口座の使い分けを読む ›</a></p></section>'''
