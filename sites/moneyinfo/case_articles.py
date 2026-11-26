"""Three reader-facing model cases, with editorial sources kept outside site/."""
from html import escape
from case_finances import (CHECKED, RAIL, STAY, BUS, TOGETHER, RESERVED, RESERVED_TRIP, RENT_USED, RENT_NEW, BUY, RECYCLE, STAMP,
                           BROKERAGE_LIMIT, DOWN_PAYMENT, HOUSE_KNOWN, TRAVEL_OVERNIGHT,
                           TRAVEL_DAY, DELI_TWO, COOK_TWO, DELI_DELIVERY, SMALL_ORDER_SHIPPING,
                           FROZEN_FEE, RICE_TWO, SIDE_TWO, SOUP_TWO, DINNER_COMMON,
                           DINNER_DELI, DINNER_COOK, DINNER_DELIVERY, BUY_COMPARABLE, BUY_SETUP,
                           BUY_RECYCLE, BUY_TRANSPORT, BUY_VISIT, BUY_ALL, profile_html, yen)


CASES = (
    {
        "slug": "case-family-trip", "theme": "帰省・旅行", "household": "子どもがいる世帯", "tag": "共働き・小学生のいる家庭",
        "title": "帰省費用の見積もり方　東京〜京都の新幹線と宿",
        "lead": f"東京〜京都へ帰省する家族3人なら、この例では新幹線往復、素泊まり、宿までの市バスで{yen(TOGETHER)}。実家に泊まる場合との差を計算します。",
        "amount": f"往復・素泊まり・宿までのバス {yen(TOGETHER)}（東京〜京都・家族3人）",
        "checked": CHECKED,
        "related": (("tools.html#savings", "帰省までの毎月の準備額を計算する"), ("basics-household.html", "年に数回の支出を家計に入れる"), ("travel-cost-average.html", "帰省費用の平均と自分の見積もりの違いを読む")),
        "alt": "食卓で帰省の旅程を相談する夫婦と小学生の子ども",
        "points": (
            "東京〜京都の新幹線で、普通車自由席を使う場合の往復は家族3人で66,600円です。",
            f"3人1室の素泊まりと宿までのバス代を足すと{yen(TOGETHER)}。食事や観光時の移動は別です。",
            "セットを調べるときは、同じ人数・泊数で、座席と取消条件も確認しましょう。",
        ),
        "sections": (
            ("帰省に一泊を足す家族の予定", "30代の共働き夫婦と小学生の子どもが東京から京都へ。実家で昼食を取り、市内の宿に泊まり、翌日は観光して夕方に帰ります。子どもも一人分の寝具を使い、食事は別に用意します。"),
            ("新幹線の往復は家族で66,600円", "普通車自由席の片道は、13,320円（大人）と6,660円（子ども）です。大人2人・子ども1人で往復すると、（13,320円×2人＋6,660円）×2＝66,600円。東京駅〜京都駅間の列車代の例で、宿代や自宅から駅までの交通費は別です。指定席を取る場合や全席指定の列車に乗る場合は、その指定席の料金で計算し直します。"),
            ("家族3人で泊まる場合と実家へ帰る場合", f"市内の3人部屋を通常日に借りる例は、大人4,200円が2人、小学生3,550円が1人。宿泊税200円を3人分加えると{yen(STAY)}です。京都駅から宿までの市バス往復は、大人片道230円、小学生120円で{yen(BUS)}。自由席の列車も合わせると{yen(TOGETHER)}です。実家泊で宿代がかからなければ、同じ列車代の{yen(RAIL)}に実家までの移動費を足します。食事・観光時の移動・手土産は別です。"),
            ("宿と列車の条件をそろえて比べる", f"別々に手配する場合は列車代に家族全員の宿代と現地移動費を加えます。例えば通常期の「のぞみ」指定席をネット予約する例は大人片道13,970円、小学生6,980円。家族の往復{yen(RESERVED)}と同じ宿・バスで{yen(RESERVED_TRIP)}です。セットと比べるときは、同じ日程・列車・部屋・食事をそろえ、セット代に現地で別払いの税や交通費を足します。子どもの料金区分は交通と宿で別々に確認します。添い寝でも施設で別払いとなる費用がないか調べてください。"),
            ("手土産や立て替えを分ける", "列車代・宿代のほかに、食事や手土産などに使う金額も書き出します。家族で負担を分けるなら、全員分の支払総額と、自分の家計から出す額を別に記録します。先に立て替える場合は、支払日と精算日も控えておきましょう。"),
            ("予定が変わったときの費用", "実家の都合で日程が変わる場合を考えます。取り消す際に、列車と宿のどちらに費用がかかるか、セットは一部だけ変更できるかを確認します。支払総額と、取り消した場合に戻る金額を別々に書いておきましょう。"),
            ("次の行動　同じ日程で見積もる", "往復に使う駅と泊まる日、家族全員の人数をメモしたら、別々に取る場合とセットの両方を調べます。金額が近ければ、帰りの時間と取消条件も見て選びましょう。実家に泊まれる場合は、交通費だけの案も残しておけます。"),
        ),
    },
    {
        "slug": "case-weeknight-dinner", "theme": "日常の家計", "household": "夫婦のみ", "tag": "共働き・出社日が増えた家庭",
        "title": "共働きの夕食費　出社日が増えた月の計算方法",
        "lead": "出社日の夕食費がいくら変わるかは、夕食1回の差額と出社日数から試算できます。惣菜・作り置き・宅配の費目をそろえ、初回と継続時の費用を分けます。",
        "amount": f"同じ献立の夕食2人分　自宅調理 {yen(DINNER_COOK)}・惣菜 {yen(DINNER_DELI)}",
        "checked": CHECKED,
        "related": (("basics-household.html", "毎月の食費を家計に組み込む"), ("basics-shopping.html", "送料まで含めた支払額を確認する")),
        "alt": "台所で惣菜を皿に移し、ご飯を並べる共働きの夫婦",
        "points": (
            f"夕食2人分の試算は、自宅調理{yen(DINNER_COOK)}、店頭惣菜{yen(DINNER_DELI)}、宅配{yen(DINNER_DELIVERY)}です。",
            "定期宅配の本州向け送料の例は、税抜2,000円未満の注文で1,200円です。",
            "同じ人数・食数にそろえ、追加の食材と調理にかかる時間も記録します。",
        ),
        "sections": (
            ("帰宅が遅い日だけを振り返る", "40代の共働き夫婦。出社日が増え、夕食を帰り道で買う日が増えました。まず、出社した日のレシートから夕食分を拾います。昼食や休日の買い物を除けば、見直したい支出が見えてきます。"),
            ("出社日が増えた月の夕食費を試算する", "いつもの夕食と、出社日に用意する夕食の税込総額を、同じ人数・同じ献立の範囲で比べます。月の差額は「出社日の夕食代と普段の夕食代の差 × その月に増えた出社日数」。週に1日増えて、対象の曜日がその月に4回なら4回分です。祝日や在宅勤務へ切り替えた日を除き、実際に夕食の用意が変わった日を数えます。"),
            ("おためしと継続時の費用を分ける", "食材宅配のおためしセットの掲載例は税込1,980円で、送料はかかりません。通常の定期宅配は条件が異なります。定期会員の本州向けでは、税抜2,000円未満で送料1,200円、2,000〜4,499円で600円、4,500〜6,499円で300円、6,500円以上で送料はかかりません。冷凍手数料は送料と別です。初回の代金をそのまま毎週の予算に入れないようにしましょう。"),
            ("大人2人分の献立をそろえて比べる", f"献立はさばの塩焼き、ご飯、ひじき煮、みそ汁です。どの方法でも、ご飯2食{yen(RICE_TWO)}と、2人で分けるひじき煮1袋{yen(SIDE_TWO)}を店頭で買い、みそ汁は12食入りのうち2食分{yen(SOUP_TWO)}を使います。共通の食費は{yen(DINNER_COMMON)}です。"),
            ("自宅調理・店頭惣菜・宅配の合計", f"自宅で焼くなら塩さば2切{yen(COOK_TWO)}を足して{yen(DINNER_COOK)}。店頭の加熱済み惣菜なら2切{yen(DELI_TWO)}を足して{yen(DINNER_DELI)}です。本州の定期会員が宅配で加熱済みのさば2切{yen(DELI_DELIVERY)}だけを注文する場合、送料{yen(SMALL_ORDER_SHIPPING)}と共通の食費を含めて{yen(DINNER_DELIVERY)}。冷凍手数料がかかる条件なら{yen(DINNER_DELIVERY + FROZEN_FEE)}です。表示された税込単価による試算です。切身の大きさは商品ごとに異なります。会計時の端数処理、調理の光熱費、買い物の交通費は試算に含めていません。"),
            ("同じ食数で、食費と時間を比べる", "二人分の夕食を同じ回数で比べます。惣菜は追加する主食などを、作り置きは使った食材を、宅配は送料と足りない食材を加えます。宅配の箱に入った品数は、夕食をまかなえる回数と同じとは限りません。受け取りから配膳までにかかった時間も書いておきます。"),
            ("次の行動　使う日を決めてから試す", "宅配を試すなら、食べる人数、献立、受取日、送料を含む支払額を確認します。帰宅が遅くて調理が難しい日には惣菜も使えます。試した後は、実際に何食に使えたかを見て、続けるか考えましょう。"),
        ),
    },
    {
        "slug": "case-temporary-appliances", "theme": "仕事・転居", "household": "単身で赴任", "tag": "会社員・期限付きの単身赴任",
        "title": "単身赴任の家電費用　洗濯機を90日借りる料金例",
        "lead": "容量4.2kgの洗濯機を90日借りる場合、中古の料金例は13,750円。必要な家電を絞り、配送や退去時の費用も含めて見積もります。",
        "amount": "洗濯機の90日レンタル例 13,750円（中古・4.2kg）",
        "checked": CHECKED,
        "related": (("basics-work.html", "勤務先の手当や立て替えの条件を確認する"), ("tools.html#savings", "赴任前に準備する金額を計算する")),
        "alt": "赴任先の部屋で洗濯機を置く場所を測る会社員",
        "points": (
            "容量4.2kgの洗濯機を90日借りる掲載例は、中古13,750円、新品26,400円です。",
            f"新品を買い、退去時の引き取りまで頼む料金を積み上げると{yen(BUY_ALL)}からです。",
            "借りる場合は配送先と返却日を確認し、赴任が延びたときの費用も調べます。",
        ),
        "sections": (
            ("赴任先にある物から調べる", "30代の会社員に東京都新宿区への90日間の単身赴任が決まりました。帰任後の自宅では洗濯機を置く場所を取れません。まず会社に、社宅の備品、家電の購入やレンタルに使える補助、先に立て替える金額を聞きました。"),
            ("家電セットは必要な品だけの見積もりと比べる", "冷蔵庫や電子レンジも必要なら、セットの内訳から備え付けの品を除きます。足りない品だけを単品で借りた額と、セットの支払総額を同じ期間で比べます。立て替えに必要な額と最終的な自己負担は、会社に精算できる分を分けて計算しましょう。"),
            ("90日分のレンタル料金を比べる", f"容量4.2kgの全自動洗濯機を90日借りる税込料金例は、中古{yen(RENT_USED)}、新品{yen(RENT_NEW)}です。新宿区の無料配送エリアで通常の配送・設置・回収を頼み、時間指定などの有料オプションを付けない条件では、それぞれの額が90日分の合計です。"),
            ("購入して退去日に引き取ってもらう費用", f"新宿区の配送可能エリアで、容量4.5kgの全自動洗濯機を新品で買い、90日後に購入店に回収だけを頼む場合の例です。本体{yen(BUY_COMPARABLE)}、通常の配送・設置{yen(BUY_SETUP)}、リサイクル料{yen(BUY_RECYCLE)}、収集・運搬{yen(BUY_TRANSPORT)}、回収のみの出張費{yen(BUY_VISIT)}から。公開料金を足すと{yen(BUY_ALL)}からです。追加工事がいる部屋や搬出が難しい部屋は、事前に見積もりを取ります。"),
            ("自分で持ち込む場合と備え付けの場合", f"別の4.5kgの機種では、本体の公表価格{yen(BUY)}と、指定引取場所に自分で持ち込む際のリサイクル料{yen(RECYCLE)}を合わせて{yen(BUY + RECYCLE)}です。配送・設置、退去時に自分で運ぶ費用、リサイクル券の払込手数料を別に見積もります。同じ家賃で備え付けの洗濯機を使えるなら、本体への追加支出は0円です。家賃が違うなら90日分の差を足します。"),
            ("次の行動　返す日と延長費用を調べる", "設置場所の幅と奥行き、蛇口と排水口の位置を確認し、必要な機種だけ見積もります。90日で返す場合と赴任が延びた場合の費用、退去日に回収できるかを聞いておきましょう。月額のサービスは、最低利用期間と途中解約にかかる費用を調べ、赴任期間に合う場合に候補へ入れます。"),
        ),
    },
    {
        "slug": "article", "image": "case-housing", "theme": "住宅購入",
        "household": "子どもがいる世帯", "tag": "共働き・住宅購入",
        "title": "住宅購入の頭金と諸費用　共働き世帯の資金計画",
        "lead": "4,000万円の中古戸建てを買うモデルケース。頭金と諸費用の支払日を分け、引渡し後に残したい生活資金から計画を立てます。",
        "amount": f"頭金と確認済みの諸費用 {yen(HOUSE_KNOWN)}（上限の仲介料を仮置き）",
        "checked": CHECKED, "alt": "家のテーブルで住宅資金の予定を相談する二人",
        "related": (("tools.html#savings", "頭金と諸費用を準備する月額を計算する"), ("basics-household.html", "住宅購入後の年払いを家計に入れる")),
        "points": (
            "売買価格は4,000万円。頭金200万円のうち手付金を100万円と置くモデルです。",
            f"紙の契約書の印紙税は{yen(STAMP)}。仲介手数料を上限の{yen(BROKERAGE_LIMIT)}で置くと、頭金とこの2費目の計は{yen(HOUSE_KNOWN)}です。",
            "登記・借入・引越しの見積もりと、引渡し後に残す生活資金は別枠です。",
        ),
        "sections": (
            ("住まいの条件と購入の前提", "機械設計と人事事務の仕事をする夫婦と小学生の世帯です。個人の売主から中古戸建てを購入する例で、計算に使う売買価格は4,000万円。借入の可否や毎月の返済額はこのケースでは決めていません。"),
            ("契約時に払うお金", "手付金100万円を契約時に払い、引渡し時に売買代金へ充当する契約を仮定します。2027年3月31日までに作成する、対象となる4,000万円の紙の不動産売買契約書は、軽減適用時に印紙税1万円です。手付金と印紙税を合わせ、この時点の支出例は101万円。仲介料の支払日は媒介契約を読みましょう。"),
            ("引渡し時に残りの頭金と諸費用を払う", "この世帯は頭金の半分を手付金として先に支払います。残り100万円は引渡し時に用意します。買主側の仲介手数料の上限は、売買価格の3％に6万円を足し、さらに消費税を加えて求めます。このケースでは138万6,000円です。上限を全額支払う仮定で、頭金・印紙税・仲介料の合計は339万6,000円です。"),
            ("引渡しの後に残すお金", "預貯金600万円から、頭金とこの2費目を払うと260万4,000円残る試算です。この残額から登記、住宅ローンの手数料、火災保険、引越しなどの見積もりを差し引きます。住み始めてからは返済だけでなく、税・保険と修繕用の積立も家計に入れます。"),
            ("次の行動　見積もりを支払日順に置く", "仲介、登記、借入、保険、引越しの見積もりを別々に取り、支払日を一枚に書きます。生活用に残す資金を先に差し引き、契約前に現金が足りるかを確認します。"),
        ),
    },
)


from consult_articles import CONSULT  # noqa: E402  the consultation-type articles (consult/*.md), newest first
import year_end_article  # noqa: E402
CASES = (year_end_article.build(), *CONSULT, *CASES)


AVERAGE = {
    "slug": "travel-cost-average", "image": "case-family-trip",
    "tag": "帰省・旅行の基礎", "theme": "帰省・旅行", "household": "",
    "title": "帰省費用の平均はいくら？ 宿泊と日帰りの違い",
    "lead": f"2025年の国内の帰省・知人訪問などは、1人1回あたり宿泊{yen(TRAVEL_OVERNIGHT)}、日帰り{yen(TRAVEL_DAY)}。家族の旅行費は人数・宿・移動手段から見積もり直します。",
    "checked": CHECKED, "alt": "食卓で帰省の旅程を相談する家族",
    "related": (("case-family-trip.html", "家族3人の新幹線と宿泊費のケースを読む"),),
    "points": (
        f"2025年の国内の帰省・知人訪問などは、宿泊で1人1回{yen(TRAVEL_OVERNIGHT)}です。",
        f"同じ目的でも日帰りの場合は、1人1回{yen(TRAVEL_DAY)}です。",
        "家族分を見積もるときは、子どもの料金と宿泊先を分けます。",
    ),
    "sections": (
        ("宿泊と日帰りの平均の範囲", "対象は国内居住者の国内旅行で、旅行の目的が帰省・知人訪問などに当たるものです。交通費だけの集計ではなく、宿泊や飲食、買い物などの支出を含みます。宿泊の平均には有料の宿に泊まる旅行と実家などに泊まる旅行が両方含まれます。"),
        ("家族の予算は人数と宿で見積もる", "平均に人数を掛けるだけでは、子どもの区分や宿の有無が反映されません。往復の交通費を人数ごとに出し、宿泊するなら部屋代と税を加えます。現地での移動、食事、手土産は別に書き、先に払う費用も確認します。"),
        ("誰がいくら用意するかを決める", "参加者全員の総額と自分の家計が払う額を分けます。立て替えが必要なら、予約時の支払額と後日の精算額も書いておくと、出発前に用意する額を判断できます。"),
    ),
}


def case_filters():
    def options(key):
        return "".join(f'<option>{escape(value)}</option>'
                       for value in dict.fromkeys(c[key] for c in CASES))
    return f'''<div class="case-filters" id="case-filters" hidden>
<label>テーマ<select id="case-theme"><option value="">すべて</option>{options("theme")}</select></label>
<label>世帯・状況<select id="case-household"><option value="">すべて</option>{options("household")}</select></label>
<p id="case-count" role="status"></p></div>'''


def cards():
    return "".join(
        f'<a class="case-index-card" data-case-theme="{escape(c["theme"], quote=True)}" data-case-household="{escape(c["household"], quote=True)}" href="{c["slug"]}.html">'
        f'<img src="assets/{c.get("image", c["slug"])}.webp" alt="" width="1200" height="600" loading="lazy">'
        f'<div><span class="entry-tag">{escape(c["tag"])}</span>'
        f'<h3>{escape(c["title"])}</h3><p class="case-card-amount">{escape(c["amount"])}</p>'
        + (f'<p class="case-card-condition">{escape(c["condition"])}</p>' if c.get("condition") else "") +
        f'<p class="case-card-date">確認日 {escape(c["checked"])}</p>'
        '<span class="entry-more">記事を読む ›</span></div></a>'
        for c in CASES
    )


QUOTE_FIELDS = {
    "case-family-trip": (
        "同じ条件で取った旅行の見積もりを比べる",
        "大人2人・小学生1人の同日程、同じ座席・食事・部屋条件で比較します。宿泊税、別払いの乗車区間、現地移動を両方に含めた最終額を入力してください。",
        ("列車と宿を別々に取る総額", "列車と宿のセットの総額"),
        ("別々の手配", "セット"),
    ),
    "case-temporary-appliances": (
        "購入と90日レンタルの最終額を比べる",
        "東京都新宿区への配送・設置と、退去時の運搬・回収やリサイクルまで含めます。会社の精算や売却額を差し引く場合は、金額が確定した分だけ両案に反映してください。",
        ("購入して90日使う総額", "90日レンタルの総額"),
        ("購入", "レンタル"),
    ),
}


def quote_form(slug):
    if slug not in QUOTE_FIELDS:
        return ""
    title, help_text, fields, options = QUOTE_FIELDS[slug]
    inputs = "".join(
        f'<label>{escape(label)}（円）<input type="number" min="0" max="100000000" step="1" inputmode="numeric" name="{name}" required></label>'
        for label, name in zip(fields, ("first", "second"))
    )
    return f'''<section class="guide-section case-quote" id="quote-compare"><h2>{escape(title)}</h2>
<p>{escape(help_text)}</p><form data-quote-compare data-first="{options[0]}" data-second="{options[1]}" hidden>
<div class="quote-fields">{inputs}</div>
<button type="submit" class="button">入力した総額を比べる</button>
<output aria-live="polite"></output>
</form><noscript>入力による試算にはJavaScriptが必要です。</noscript></section>'''


def consult_article(case):
    points = "".join(f"<li>{escape(p)}</li>" for p in case["points"])
    related = "".join(f'<a href="{href}">{escape(label)} ›</a>' for href, label in case["related"])
    checked = case["checked"].replace("-", "年", 1).replace("-", "月", 1) + "日"
    return f'''<main class="wrap model-article consult-article" id="main">
<nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span>›</span><a href="cases.html">モデルケース</a><span>›</span><span aria-current="page">{escape(case["title"])}</span></nav>
<article><header class="guide-article-header"><span class="entry-tag">{case["kind"]} · {escape(case["tag"])}</span>
<h1>{escape(case["title"])}</h1><p>{escape(case["lead"])}</p></header>
<figure class="consult-hero"><img src="assets/{case["hero"]}.webp" alt="{escape(case["hero_alt"], quote=True)}" width="1536" height="768" fetchpriority="high"></figure>
<section class="model-points"><h2>この記事の要点</h2><ul>{points}</ul><p>制度・金額の確認日 {checked}</p></section>
<nav class="guide-toc" aria-label="目次"><h2>目次</h2><ol>{case["toc_html"]}</ol></nav>
{with_ads(case["slug"], case["body_html"])}
<footer class="model-back"><h2>次に確認すること</h2><div class="related-grid">{related}</div><a href="cases.html#readable-cases">ほかのモデルケースを読む ›</a></footer></article></main>'''


VC = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788870&pid="
# approved partnerships of this site (ValueCommerce site 3788870). Only the approved, designed places carry a link.
ADS = {
    "case-family-trip": (
        {"pid": "892753631", "text": "国内の宿を探す"},
        {"pid": "892753632", "text": "ホテルを検索する"},
        {"pid": "892753633", "text": "ホテル・旅館の予約を見る"},
    ),
}


ADS["travel-cost-average"] = ADS["case-family-trip"]      # the same lodging services close the average-cost page


def ad_html(slug):
    ads = ADS.get(slug)
    if not ads:
        return ""
    items = "".join(
        f'<li><a href="{VC}{a["pid"]}" rel="nofollow sponsored noopener" target="_blank">{escape(a["text"])}</a></li>' for a in ads)
    lead = "宿を別々に手配する場合は、日程と人数を決めてから、複数のサービスで料金と取消条件を同じ基準で見比べます。条件を入れて探すときは、次のリンクが使えます。"
    return f'<aside class="ad-box" aria-label="広告"><p class="ad-label">PR（広告）</p><p>{lead}</p><ul>{items}</ul></aside>'


# AccessTrade (media 1170676). The issued href, rk and measurement image are never changed (the ASP forbids editing the code).
# {slug: ((heading of the section the box closes, rk, reason sentence, link words), ...)}
AT_ADS = {
    "case-year-end-expenses": (
        # CFOne (approved 2026-11-25). Forbidden by the advertiser: anything that reads as "leave it all to us" or a promised saving.
        ("年内に買う物を絞る", "0100q8lb00p3as",
         "申告を自分で進めるときの相談先の一つに、会計事務所の無料相談があります。対象は、法人なら役員のみで年商1億円未満・国内取引が中心の場合、個人事業主なら所得が事業・給与・退職のみの場合です。",
         "申告の無料相談の対象と内容を確認する"),
    ),
    "case-first-living": (
        ("これから必要になるお金と時期", "0100q8vc00p3as",
         "引っ越しの費用は、荷物の量と時期で変わります。物件が決まったら、早めに手配の方法と料金を確認してください。", "引っ越しポルタで引っ越しの手配を調べる"),
        ("ご提案2", "0100q7ix00p3as",
         "毎月の通信費には自宅のネット回線も入ります。光回線を引くときは、税込の月額総額と開通までの日数を、申し込みの前に確認してください。", "BIGLOBE光プラスの条件を確認する"),
    ),
}


def at_box(rk, lead, text):
    return (f'<aside class="ad-box" aria-label="広告"><p class="ad-label">PR（広告）</p><p>{escape(lead)}</p><p>'
            f'<a href="https://h.accesstrade.net/sp/cc?rk={rk}" rel="nofollow sponsored noopener" referrerpolicy="no-referrer-when-downgrade" target="_blank">'
            f'{escape(text)}<img src="https://h.accesstrade.net/sp/rr?rk={rk}" width="1" height="1" border="0" alt=""></a></p></aside>')


def a8_link(mat, server, text):
    """A8.net as issued (the link words and the 1x1 picture are not changed); only rel and target are added."""
    return (f'<a href="https://px.a8.net/svt/ejp?a8mat={mat}" rel="nofollow sponsored noopener" target="_blank">{escape(text)}</a>'
            f'<img border="0" width="1" height="1" src="https://{server}.a8.net/0.gif?a8mat={mat}" alt="">')


def yahoo_link(text):
    """ValueCommerce free text (Yahoo! Shopping): the words may be ours; the address and the measurement picture are as issued."""
    ids = "sid=3788870&pid=892757587"
    return (f'<a href="//ck.jp.ap.valuecommerce.com/servlet/referral?{ids}" rel="nofollow sponsored noopener" target="_blank">'
            f'<img src="//ad.jp.ap.valuecommerce.com/servlet/gifbanner?{ids}" height="1" width="1" border="0" alt="">{escape(text)}</a>')


# {slug: ((heading of the section the box closes, reason sentence, (link html, ...)), ...)}
LINK_ADS = {
    "case-year-end-expenses": (
        ("取得価額で経費への入れ方を確認する",
         "取得価額と使い始めた日は、帳簿に残しておきます。会計ソフトで記帳する場合は、料金と対応する申告の区分を申し込みの前に比べてください。",
         (a8_link("4BGSTF+247PXE+4JGQ+BZ8OY", "www15", "はじめてでも安心のサポート体制 マネーフォワード クラウド確定申告"),
          a8_link("4BGSTF+201OOY+35XE+5YJRM", "www14", "やよいの青色申告オンライン"))),
        ("仕事で使う日から納品と注文を逆算する",
         "注文する前に、在庫と届け先を入れて到着予定日を確認します。年内に使い始められる日に届くかどうかを基準に選んでください。",
         (yahoo_link("仕事用の備品をYahoo!ショッピングで探す"),)),
    ),
}


def link_box(lead, links):
    items = "".join(f"<li>{link}</li>" for link in links)
    return f'<aside class="ad-box" aria-label="広告"><p class="ad-label">PR（広告）</p><p>{escape(lead)}</p><ul>{items}</ul></aside>'


def with_ads(slug, body):
    """Close the designed section with its advertisement box; a missing section stops the build."""
    boxes = [(heading, link_box(lead, links)) for heading, lead, links in LINK_ADS.get(slug, ())]
    boxes += [(heading, at_box(rk, lead, text)) for heading, rk, lead, text in AT_ADS.get(slug, ())]
    for heading, box in boxes:
        start = body.find(f"<h2>{heading}")
        end = body.find("</section>", start)
        if start < 0 or end < 0:
            raise ValueError(f"{slug}: no section for the advertisement: {heading}")
        body = body[:end] + box + body[end:]
    return body


def article(case):
    if case.get("consult"):
        return consult_article(case)
    points = "".join(f"<li>{escape(p)}</li>" for p in case["points"])
    toc = "".join(f'<li><a href="#part-{i}">{escape(h)}</a></li>'
                  for i, (h, _) in enumerate(case["sections"], 1))
    body = "".join(f'<section class="guide-section" id="part-{i}">'
                   f'<h2>{escape(h)}</h2><p>{escape(p)}</p></section>'
                   for i, (h, p) in enumerate(case["sections"], 1))
    slug = case["slug"]
    quote = quote_form(slug)
    if quote:
        toc += f'<li><a href="#quote-compare">{QUOTE_FIELDS[slug][0]}</a></li>'
    visual = case.get("image", slug)
    profile = profile_html(slug) if slug != "travel-cost-average" else ""
    if profile:
        toc = '<li><a href="#household-profile">この世帯の家計と見直せるところ</a></li>' + toc
    kind = "モデルケース" if profile else "費用の基礎"
    checked = case["checked"].replace("-", "年", 1).replace("-", "月", 1) + "日"
    related = "".join(f'<a href="{href}">{escape(label)} ›</a>'
                      for href, label in case["related"])
    return f'''<main class="wrap model-article" id="main">
<nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span>›</span><a href="cases.html">モデルケース</a><span>›</span><span aria-current="page">{escape(case["title"])}</span></nav>
<article><header class="guide-article-header"><span class="entry-tag">{kind} · {escape(case["tag"])}</span>
<h1>{escape(case["title"])}</h1><p>{escape(case["lead"])}</p></header>
<figure class="model-hero"><img src="assets/{visual}.webp" alt="{escape(case["alt"], quote=True)}" width="1200" height="{396 if slug == 'article' else 600}"><figcaption>イメージです。</figcaption></figure>
<section class="model-points"><h2>この記事の要点</h2><ul>{points}</ul><p>料金の確認日 {checked}</p></section>
<nav class="guide-toc" aria-label="目次"><h2>目次</h2><ol>{toc}</ol></nav>
{profile}{body}{ad_html(slug)}{quote}
<footer class="model-back"><h2>次に確認すること</h2><div class="related-grid">{related}</div><a href="cases.html#readable-cases">ほかのモデルケースを読む ›</a></footer></article></main>'''
