"""The three features of the new design: pass-rate data (/goukaku-ritsu/), readings (/yomimono/ and the article /cbt/), entrance exams (/tokushu-nyushi/)."""
from __future__ import annotations

import json
import math

from . import common, ics, ui
from .common import TODAY, d, jp, md, left, rel, ver, today_j, DESIGN_DATE
from .model import BY_ID, events_of, pass_rate_rows, applicant_basis_rate, sit_rate, when_text
from .pages_v2 import CHECK, FEE_RANGE, FEE_ROWS, a, cal_buttons, data_blob, esc, fix, fy_label, page, sec


def _ld(*objs) -> str:
    return "".join('<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False).replace("</", "<\\/") + "</script>" for x in objs)


# ---------------------------------------------------------------- feature: pass-rate data
def goukaku_ritsu() -> dict:
    from .pages_deep import goukaku_ritsu as old
    prev = old()                                                   # the table and the chart of the nine exams, and two short sections, are kept
    rows5 = pass_rate_rows("takken", 5)
    cur = rows5[0]
    ex, ap, ps = cur["examinees"], cur["applicants"], cur["passers"]
    r_ex, r_ap = ps / ex * 100, applicant_basis_rate(cur)
    y = fy_label(cur["year"])

    intro = ('<p class="sec-sub">' + fix("合格率データ", "合格率は、試験の難しさを比べるためによく使われます。ただし、割り算の分母が違うと、同じ試験でも数字が変わります。この特集では、宅建の実数を使って、その違いをそのまま見せます。",
                                      "合格率は、試験の難しさを比べるときによく使われます。ただし、割り算の分母が違うと、同じ試験でも数字が変わります。この特集では、宅建の実数で、その違いを解説します。",
                                      "「比べるためによく使われます」は、比べる目的が先に来て、次の「ただし」とつながりにくい。「そのまま見せます」の「そのまま」は何を指すか分からない") + '</p>')
    lo, hi = min(r["rate"] for r in rows5), max(r["rate"] for r in rows5)
    bar_rows = [{"label": fy_label(r["year"]), "value": r["rate"]} for r in rows5]
    tbl = ui.table(["年度", "申込者", "受験者", "合格者", "合格率（受験者基準）"],
                   [[fy_label(r["year"]), f'{r["applicants"]:,}', f'{r["examinees"]:,}', f'{r["passers"]:,}', f'{r["rate"]:.1f}%'] for r in rows5], "宅建士試験 直近5回の結果", num=(1, 2, 3, 4))
    s1 = (intro + '<h2>宅建の合格率の推移（直近5回）</h2>'
          f'<p class="sec-sub">合格率は{int(lo)}〜{int(hi) + 1}％の範囲で動いています。下のグラフと表は、{a("/takken/", "宅建の詳細ページ")}と同じデータです。</p>'
          + ui.bars(bar_rows, "宅建の合格率の推移（受験者基準・単位は％）") + '<p class="hint">棒グラフの数字は、合格率（合格者 ÷ 受験者）で、単位は％です。</p>' + tbl)

    s2 = ('<h2>合格率は「合格者 ÷ 受験者」で計算します</h2>'
          f'<p>一般に、試験の合格率は、合格者の数を、実際に試験を受けた受験者の数で割って計算します。宅建・{y}では、合格者が{ps:,}人、受験者が{ex:,}人です。'
          f'{ps:,} ÷ {ex:,} = {ps / ex:.4f}…となり、合格率は{r_ex:.1f}％になります。これが、実施団体が発表する合格率です。</p>'
          f'<h3>申込者で割ると、数字は約{r_ap:.1f}％になります</h3>'
          f'<p>同じ合格者{ps:,}人を、申込者の数{ap:,}人で割ると、{ps:,} ÷ {ap:,} = 約{ps / ap:.4f}、つまり約{r_ap:.1f}％になります。申込だけして受験しなかった分も分母に入るため、数字は小さくなります。'
          f'{y}は、申込者のうち実際に受験した割合（受験率）が{sit_rate(cur):.1f}％でした。残りの約{round((100 - sit_rate(cur)) / 10)}割は、申し込んだものの受験しなかったことになります。</p>'
          '<div class="compare"><div class="cmp official"><b>受験者基準（宅建の公式の合格率）</b>'
          f'<p>{ps:,} ÷ {ex:,}</p><div class="big">{r_ex:.1f}％</div></div>'
          f'<div class="cmp"><b>申込者基準（参考の計算）</b><p>{ps:,} ÷ {ap:,}</p><div class="big">約{r_ap:.1f}％</div></div></div>'
          + ui.bars([{"label": "受験者基準（公式）", "value": round(r_ex, 1)}, {"label": "申込者基準（参考）", "value": round(r_ap, 1)}], "同じ合格者数を、受験者と申込者で割った合格率の比較（単位は％）")
          + '<h3>基準が違う数字は、そのまま比べられません</h3>'
          '<p>あるサイトが受験者基準で18.7％と書き、別のサイトが申込者基準で約15.0％と書くと、同じ試験なのに数字が食い違って見えます。どちらかが間違っているのではなく、分母が違うだけです。'
          '合格率を比べるときは、まず「合格者 ÷ 受験者」なのか「合格者 ÷ 申込者」なのかをご確認ください。基準がそろっていない数字同士では、難しさの比較にはなりません。</p>'
          '<div class="rule-box"><b>このサイトの決め方</b><br>合格率は、実施団体が発表する「合格者 ÷ 受験者」の数字です。申込者基準の数字には、そのことが分かるよう注を添えます。</div>')
    fix("合格率データ", "この違いが、この特集の独自の論点です。", "（この一文を削った。次の文が同じことを言っている）", "『独自の論点』は、読者に役立つ情報を足さず、サイト側の自画自賛に読める")

    n_fee = f'{FEE_RANGE[0][1]:,}'
    grows = all(rows5[i]["applicants"] > rows5[i + 1]["applicants"] for i in range(4))
    prev_row = rows5[1]
    s3 = ('<h2>データで見る、ほかの数字</h2><div class="bignums">'
          f'<div class="bignum"><div class="num">{sit_rate(cur):.1f}<small> ％</small></div><h3>宅建の受験率（{y}）</h3><p>受験者{ex:,}人 ÷ 申込者{ap:,}人です。申込者の約2割は受験していません。</p></div>'
          f'<div class="bignum"><div class="num">{FEE_RANGE[0][1]:,}<small> 円</small>〜{FEE_RANGE[1][1]:,}<small> 円</small></div><h3>受験料の範囲</h3>'
          f'<p>確かめた範囲では、{FEE_RANGE[0][0].split("（")[0]}が{FEE_RANGE[0][1]:,}円、{FEE_RANGE[1][0].split("（")[0]}が{FEE_RANGE[1][1]:,}円です。宅建は8,200円です。</p>{a("/fees/", "受験料の一覧を見る", "cardlink")}</div>'
          f'<div class="bignum"><div class="num">{ap:,}<small> 人</small></div><h3>宅建の申込者数（{y}）</h3>'
          f'<p>' + (fix("合格率データ", "申込者数は5回続けて増えています。前回（令和6年度）は301,336人でした。",
                       f"申込者数は、この5回で毎回増えています。前回（{fy_label(prev_row['year'])}）は{prev_row['applicants']:,}人でした。",
                       "5回分の数字だと、増えた回は4回。『5回続けて』は数え方が合わないので、『この5回で毎回』に直した") if grows else f"前回（{fy_label(prev_row['year'])}）は{prev_row['applicants']:,}人でした。")
          + '</p></div></div>')

    others = prev["sections"]
    tbl9 = ui.table(others[0]["table"]["cols"], [[c["text"] if isinstance(c, dict) else c for c in r] for r in others[0]["table"]["rows"]], others[0]["table"]["caption"], num=tuple(others[0]["table"].get("num_cols", ())))
    s4 = ('<h2>ほかの資格の合格率</h2><p>主な資格の最新の合格率です。どれも合格者 ÷ 受験者の数字です。回や計算のしかたが違うものは、表の下に注があります。</p>' + tbl9
          + f'<p class="hint">{esc(others[0]["table"]["note"])}</p>'
          + "".join(f'<h3>{esc(s["h2"])}</h3>' + "".join(f"<p>{esc(t)}</p>" for t in s["paras"]) for s in others[1:3]))

    tk = BY_ID["takken-result"]
    kg = BY_ID["kangoshi-deadline"]
    kn = BY_ID["kaigo-exam"]
    top_fee = FEE_ROWS[-1][0] == "介護福祉士"
    s5 = ('<h2>関連する詳細ページ</h2><div class="feature-grid">'
          f'<div class="fcard"><h3>宅建の詳細</h3><p>{("合格発表まで" + rel(tk["iso"]) + "。") if left(tk["iso"]) >= 0 else ""}日程、合格率、総コスト計算機と逆算プランナーがある詳細ページです。</p>{a("/takken/", "宅建の詳細を見る", "cardlink")}</div>'
          f'<div class="fcard"><h3>看護師国家試験（第116回）</h3><p>申込締切は{md(kg["iso"])}（{rel(kg["iso"])}）、試験日は{jp(BY_ID["kangoshi-exam"]["iso"])}、合格発表は{md(BY_ID["kangoshi-result"]["iso"])}です。</p>{a("/kangoshi/", "看護師国家試験のページを見る", "cardlink")}</div>'
          f'<div class="fcard"><h3>介護福祉士</h3><p>試験日は{jp(kn["iso"])}、受験料は20,510円です。' + ("このサイトで確かめた受験料の中では、最も高い金額です。" if top_fee else "") + f'</p>{a("/kaigo-fukushi/", "介護福祉士のページを見る", "cardlink")}</div></div>'
          f'<p>{a("/", "トップで締切を探す", "cardlink")}</p>')
    ld = _ld({"@context": "https://schema.org", "@type": "Dataset", "name": "宅建士試験の合格率（受験者基準・申込者基準）", "description": "宅地建物取引士資格試験の直近5回の申込者・受験者・合格者・合格率と、基準による数字の違い。",
              "inLanguage": "ja", "creator": {"@type": "Organization", "name": "一般財団法人 不動産適正取引推進機構"}, "dateModified": DESIGN_DATE})
    p = page("/goukaku-ritsu/", "analysis", "/", "合格率の見方", "合格率の見方｜受験者基準と申込者基準の違い・宅建の実数で解説", "合格率の見方 受験者基準と申込者基準の違い",
             f"合格率は、受験者で割るか申込者で割るかで数字が変わります。宅建の{y}は、受験者基準で{r_ex:.1f}％、申込者基準で約{r_ap:.1f}％です。実数で違いを解説し、主な資格の最新の合格率も並べました。",
             f"同じ宅建の{y}でも、受験者で割ると{r_ex:.1f}％、申込者で割ると約{r_ap:.1f}％です。合格率は、分母にどちらの数字を使うかで変わります。",
             [sec(None, s1), sec(None, s2), sec(None, s3), sec(None, s4), sec(None, s5), sec(None, ld)],
             [{"path": "/takken/", "text": "宅建の試験日と合格率"}, {"path": "/gyosei/", "text": "行政書士試験の日程と合格率"}, {"path": "/sharoshi/", "text": "社労士試験の日程と合格率"},
              {"path": "/results/", "text": "資格試験の合格発表日の一覧"}], secondary=("合格率 とは", "資格 合格率 一覧"), intent=4)
    return p


# ---------------------------------------------------------------- readings
ARTICLES = [
    ("試験の仕組み", [("/cbt/", "CBT試験とは", "ITパスポート・FP2級3級・簿記ネット試験"), ("/boki-net/", "簿記のネット試験と統一試験の違い", "日商簿記"),
                  ("/zenki-koki/", "国公立大学の前期日程と後期日程の違い", "国公立大学")]),
    ("申込", [("/postmark/", "消印有効と必着の違い", "宅建・行政書士・国家公務員"), ("/flow/", "申込から合格発表までの流れ", "宅建・行政書士・看護師ほか"), ("/fees/", "資格試験の受験料一覧", "受験料を確かめた資格")]),
    ("合格率", [("/goukaku-ritsu/", "合格率の見方", "宅建ほか")]),
    ("日程の調べ方", [("/nendo/", "来年度の日程はいつ発表されるか", "主な資格"), ("/method/", "日程の調べ方と出典", "すべて"), ("/yama/", "11月から3月の試験日", "資格・入試")]),
]


def _answers() -> dict:
    from . import pages_deep, pages_hub, pages_nyushi
    out = {}
    for m in (pages_deep, pages_hub, pages_nyushi):
        for p in m.pages():
            out[p["path"]] = p["answer"]
    return out


def yomimono() -> dict:
    ans = _answers()
    parts = []
    n = 0
    for theme, items in ARTICLES:
        cards = "".join(f'<div class="sitem"><h3>{a(href, esc(t))}</h3><p>{esc(ans[href])}</p><p class="hint">対象：{esc(tag)}</p></div>' for href, t, tag in items)
        n += len(items)
        parts.append(f'<h2>{theme}</h2><div class="shelf">{cards}</div>')
    intro = ('<p class="sec-sub">日程の一覧だけでは分からない、試験の仕組みや申込の注意がテーマです。' '')
    intro += '全部で10本あり、各特集の最後に、対象の試験の日程ページへのリンクがあります。気になる題からご覧ください。</p>'
    parts.append('<h2>一覧表で見る</h2><details class="tableview"><summary>一覧表で見る 特集の一覧を表で開く</summary>' + ui.table(["テーマ", "記事", "要約", "対象"], [[theme, a(h, esc(t)), ans[h], tag] for theme, items in ARTICLES for h, t, tag in items], "特集の一覧") + "</details>")
    return page("/yomimono/", "hub", "/", "試験の仕組みと申込の注意", "特集｜試験の仕組みと申込の注意をテーマ別に", "特集 試験の仕組みと申込の注意",
                "CBT試験、消印有効と必着、合格率の見方など、試験の仕組みと申込の注意を解説した記事を、テーマ別に並べた棚です。各記事から、対象の試験の日程ページへ進めるようにしています。",
                "試験の仕組みと、申込の注意を解説した特集の一覧です。試験の仕組み、申込、合格率、日程の調べ方の4つのテーマで探せます。",
                [sec(None, intro + "".join(parts))],
                [{"path": "/cbt/", "text": "CBT試験とは"}, {"path": "/postmark/", "text": "消印有効と必着の違い"}, {"path": "/goukaku-ritsu/", "text": "合格率の見方"}, {"path": "/", "text": "トップで締切を探す"}], intent=4)


def cbt() -> dict:
    from .pages_deep import cbt as old
    prev = old()
    fp1 = BY_ID["fp1-deadline"]
    ev = {e["id"]: e for e in events_of("takken")}
    mail_end, net_end, st = ev["takken-deadline-mail"], ev["takken-deadline-net"], ev["takken-start-mail"]
    h1_ = "CBTは、会場のパソコンで日を選んで受ける方式です"
    fix("CBT", "CBTは、テストセンターで日を選んで受ける方式です", h1_, "『テストセンター』は一部の試験の会場の呼び名。簿記のネット試験など、ほかの会場の試験もあるので、広く通じる言い方に")
    h2_ = "年1回の試験は、申込期間を逃すと翌年まで受けられません"
    h3_ = "選び方は、仕上がりの時期で変わります"
    toc = ('<nav class="toc" aria-label="目次"><b>目次</b><ol>' + "".join(f'<li><a href="#s{i}">{t}</a></li>' for i, t in enumerate((h1_, h2_, h3_), 1)) + "</ol></nav>")
    table = [r for s in prev["sections"] if s.get("table") for r in [s["table"]]][0]
    tbl = ui.table(table["cols"], [[c["text"] if isinstance(c, dict) else c for c in r] for r in table["rows"]], table["caption"])
    s1 = (f'<h2 id="s1">{h1_}</h2>'
          '<p>' + fix("CBT", "CBTは、コンピュータを使った試験の方式です。受験する人は、テストセンターの会場で、空いている日の中から受験日を選んで申し込みます。",
                      "CBTは、コンピュータを使った試験の方式です。試験は、試験会場のパソコンで受けます。空いている日の中から受験日を選んで、申し込みます。",
                      "「テストセンターの会場で、空いている日の中から…」は、一文に会場と日の選び方が入っていた。二つに分けた") + '</p>'
          '<p>試験日が1日に限られていないため、仕事や学校の都合に合わせて日を選べます。これが、この方式の特徴です。ただし、日を選べることと、いつでも受けられることは同じではありません。実施する期間や会場ごとに受けられる日には、限りがあります。受けたい時期が決まったら、早めに空き状況をご確認ください。</p>'
          + tbl + '<p>受ける日を選べる試験は、希望の日と会場に空きがあるかを、申込の前に確かめる必要があります。持ち物や当日の流れは、試験ごとに受験案内で決まっています。会場に着いてから知ることのないよう、受験案内を事前にご確認ください。</p>'
          + f'<div class="mid-card"><p class="sec-sub">同じFP技能検定でも、1級の学科試験は、日が決まっています。</p>{ui.card(fp1)}</div>')
    fix("CBT", "…FP技能検定1級学科（きんざい）の申込締切は12月1日17時30分、試験日は2027年1月24日です。（CBTを含む試験として記載）", "（日が決まっている例として、記事の中ほどのカードに回した）",
        "1級の学科は日が決まっている試験で、CBTで通年受ける試験とは別。CBTの例として並べると誤解を招く")
    CHECK.append(("CBT", "FP技能検定1級学科（きんざい）がCBTかどうか: 日が決まっている試験としてだけ書いた。CBTかどうかは公式ページで未確認"))
    s2 = (f'<h2 id="s2">{h2_}</h2>'
          f'<p>宅建のように年に1回だけ実施する試験は、申込期間が決まっています。その期間を逃すと、次の年の申込まで待つことになります。宅建の令和8年度では、申込は{md(st["iso"])}に始まり、'
          f'郵送は{md(mail_end["iso"])}、インターネットは{md(net_end["iso"])}が締切でした。締切を過ぎてから気づいても、その年の試験は受けられません。</p>'
          '<p>' + fix("CBT", "CBT方式の試験でも、実施期間の終わりが近づくと空きが少なくなります。どちらの方式でも、「申込の締切」と「自分が受ける日」は分けて考える必要があります。",
                      "CBTの試験でも、実施期間の終わりが近づくと、希望の日に空きがないことがあります。どちらの方式でも、「申込の締切」と「自分が受ける日」は別の日です。それぞれご確認ください。",
                      "『空きが少なくなります』は言い切りすぎ。『ことがあります』に。『考える必要があります』は『考えてください』に") + '</p>')
    s3 = (f'<h2 id="s3">{h3_}</h2>'
          '<p>どちらの方式が合うかは、勉強が仕上がる時期で変わります。仕上がりの見通しが立っていて、その時期に合わせて受けたい方には、日を選べるCBTが合います。試験日が先に決まっている年1回の試験は、その日に向けて逆算して勉強する進め方が合います。</p>'
          f'<p>迷うときは、まず試験日（または受けたい時期）を決めて、そこから、勉強を始める日を逆算してください。必要なペースが確認できます。{a("/takken/#planner", "宅建の詳細ページ")}には、目標日と学習時間から始める日を出す逆算プランナーがあります。</p>'
          f'<p>{a("/takken/#planner", "逆算プランナーを使ってみる", "btn solid")}</p>')
    end = ('<h2>次の特集</h2><div class="feature-grid">'
           f'<div class="fcard"><h3>{a("/postmark/", "消印有効と必着の違い")}</h3><p>郵送で申し込むとき、「消印有効」はその日に郵便局の消印が押されていれば間に合い、「必着」はその日までに届いていなければ間に合いません。</p></div>'
           f'<div class="fcard"><h3>{a("/goukaku-ritsu/", "合格率の見方")}</h3><p>受験者基準と申込者基準では、同じ試験でも合格率の数字が変わります。宅建の実数で解説します。</p></div>'
           f'<div class="fcard"><h3>関連する試験の詳細</h3><p>{a("/takken/", "宅建の日程と合格率を見る", "cardlink")}</p></div></div>'
           '<h2>特集の一覧</h2><p class="sec-sub">このサイトにある特集の題の一覧です。</p><ul class="links">'
           + "".join(f'<li>{a(h, esc(t))}</li>' for _, items in ARTICLES for h, t, _tag in items) + f'</ul><p>{a("/yomimono/", "特集をテーマ別に見る", "cardlink")}</p>')
    p = page("/cbt/", "article", "/yomimono/", "CBT試験とは", "CBT試験とは｜通年で受ける試験と年1回の試験の違い", "CBT試験とは 通年で受ける試験と年1回の試験の違い",
             prev["description"], prev["answer"],
             [sec(None, toc + s1 + s2 + s3), sec(None, end + data_blob([]))],
             [{"path": "/boki-net/", "text": "簿記のネット試験と統一試験の違い"}, {"path": "/fp/", "text": "FP技能検定の試験日"}, {"path": "/minkan/", "text": "TOEIC・漢検・ITパスポートの日程"},
              {"path": "/schedule/", "text": "資格試験日程一覧(日付順)"}], secondary=("CBT試験 とは",), intent=4)
    return p


# ---------------------------------------------------------------- feature: entrance exams
def tokushu_nyushi() -> dict:
    from .pages_hub import KOKO, _dates
    kyo = [e for e in events_of("kyotsu") if e["type"] == "exam"]
    tsu = [e for e in events_of("kyotsu-tsuishi") if e["type"] == "exam"]
    k1, k2, t1, t2 = kyo[0], kyo[1], tsu[0], tsu[1]
    todai_exam, todai_res = BY_ID["todai-exam"], BY_ID["todai-result"]
    entry_end = BY_ID["kyotsu-deadline"]
    nxt = k1
    counter = f'<div class="count"><span class="lbl">大学入学共通テストまで</span>{ui.counter(k1["iso"], "exam")}<p class="when"><b>本試験：{esc(jp(k1["iso"]))}・{esc(md(k2["iso"]))}</b></p></div>'
    btn = f'<div class="mainbtns">{cal_buttons(k1)}</div>'
    steps_ = [("出願", f'{md(entry_end["iso"])}に終了', ""), ("本試験", f'{md(k1["iso"])}・{md(k2["iso"])}', ""), ("追・再試験", f'{md(t1["iso"])}・{md(t2["iso"])}', ""),
              ("国公立 前期日程", md(todai_exam["iso"]), ""), ("合格発表", f'東京大学 {md(todai_res["iso"])}', "")]
    days_ = [entry_end["iso"], k1["iso"], t1["iso"], todai_exam["iso"], todai_res["iso"]]
    now_i = next((i for i, x in enumerate(days_) if d(x) >= TODAY), len(days_) - 1)
    lead = fix("入試", "出願は終わっています。ここから先は、本試験、追・再試験、国公立大学の前期日程、合格発表の順に進みます。",
               "出願は終わっています。ここから先は、本試験、追・再試験、国公立大学の前期日程、合格発表の順です。", "『進みます』は何が進むのか不明。順番だけを言う文に")
    hero = f'{counter}{btn}<p class="sec-sub">{esc(lead)}</p>{ui.steps(steps_, now_i)}<!--hero-end-->'
    rows = [["大学入学共通テスト 本試験", f'{jp(k1["iso"])}・{md(k2["iso"])}', ui.counter(k1["iso"], "exam", big=False), f'<span class="actions">{cal_buttons(k1)}</span>'],
            ["追・再試験", f'{jp(t1["iso"])}・{md(t2["iso"])}', ui.counter(t1["iso"], "exam", big=False), f'<span class="actions">{cal_buttons(t1)}</span>'],
            ["国公立大学 前期日程", jp(todai_exam["iso"]), ui.counter(todai_exam["iso"], "exam", big=False), "—"],
            ["合格発表の例（東京大学）", jp(todai_res["iso"]), ui.counter(todai_res["iso"], "exam", big=False), f'<span class="actions">{cal_buttons(todai_res)}</span>']]
    s_flow = ('<h2>共通テストから合格発表までの流れ</h2>' + ui.table(["区分", "日付", "残り", "カレンダー"], rows, "共通テストから合格発表まで")
              + f'<p>東京大学の合格発表は{esc(jp(todai_res["iso"]))}です。大学ごとに日が違うため、志望校の発表日は、それぞれご確認ください。</p>')
    gen = {r["pref"]: r for r in KOKO}
    eight = ["千葉県", "神奈川県", "東京都", "愛知県", "埼玉県", "北海道", "福岡県", "大阪府"]
    items = sorted(((gen[p]["general"]["exam"][0], p) for p in eight if gen[p]["general"]["exam"]))
    cards = "".join(f'<div class="ncard"><div class="nd">{ui.counter(iso, "exam", big=False)}</div><div><h3>{esc(p)}</h3><p>学力検査：{esc(_dates(gen[p]["general"]["exam"]))}</p></div></div>' for iso, p in items)
    s_koko = (f'<h2>公立高校入試 学力検査日（都道府県別）</h2><p class="sec-sub">主な8都道府県の学力検査日です。残り日数は{esc(weekday(TODAY))}時点の計算です。{len(KOKO)}都道府県分は、一覧ページにあります。</p>'
              f'<div class="near">{cards}</div><p>お住まいの都道府県の日程は、一覧ページで県を選んでご確認ください。</p>'
              f'<p>{a("/koko/", f"{len(KOKO)}都道府県から探す", "btn solid")} {a("/nyushi/", "入試カレンダーを見る", "btn")}</p>')
    todo = [("出願が済んでいるかを確かめる", f'共通テストの出願は{md(entry_end["iso"])}に終了しました。受験生本人と一緒に、済んでいるかをご確認ください。'),
            ("受験票を保管する", "受験票が届いたら、試験当日に持っていくものと一緒に保管してください。会場と集合時間も届いた時点で確認しておくと、当日に慌てません。"),
            ("本試験までの日数を一緒に数える", f'本試験は{md(k1["iso"])}・{md(k2["iso"])}で、{rel(k1["iso"])}です。カレンダーに入れておくと、家族で同じ日付を確認できます。')]
    s_todo = ('<h2>次にやること</h2><p class="sec-sub">保護者の方とも一緒に確かめられる、一般的な項目です。学校ごとの手続きは、学校や教育委員会の案内でご確認ください。</p><ul class="checklist">'
              + "".join(f'<li><span class="tick" aria-hidden="true"></span><div><b>{esc(t)}</b><span class="t">{esc(b)}</span></div></li>' for t, b in todo) + "</ul>")
    fix("入試", "出願が済んでいるかを確認する", "出願が済んでいるかを確かめる", "『確認』が三つの項目で繰り返されていた。見出しの動詞を『確かめる』にそろえて重なりを減らした")
    CHECK.append(("入試", "仕様書4.5の保護者向けチェックリストには『支払い方法』『会場までの経路』の項目例があるが、素材にないため、素材の3項目のままにした"))
    s_read = ('<h2>保護者向けの特集</h2><div class="read-grid"><div class="read-card large"><span class="tag">特集 ・ 大学入試</span><h3>国公立大学の前期日程と後期日程の違い</h3>'
              f'<p>国公立大学の一般選抜は、前期日程と後期日程などに分かれています。前期日程は{jp(todai_exam["iso"])}です。前期と後期では、試験の日も合格発表の時期も違います。志望校ごとに日程をご確認ください。</p>'
              f'{a("/zenki-koki/", "記事を読む", "cardlink")}</div><div class="read-side">'
              f'<div class="read-card"><h3>資格試験のページも見る</h3><p>ご家族が資格試験を受ける場合は、トップの締切一覧で残り日数を確認できます。</p>{a("/", "トップへ", "cardlink")}</div>'
              f'<div class="read-card"><h3>宅建の詳細ページ</h3><p>大人の資格試験の例として、宅建の詳細ページには、日程と合格率があります。</p>{a("/takken/", "宅建を見る", "cardlink")}</div></div></div>')
    fix("入試", "国公立大学の一般選抜は、前期日程と後期日程に分かれています。", "国公立大学の一般選抜は、前期日程と後期日程などに分かれています。", "公立大学には中期日程もある。『分かれています』と言い切らず『など』を足した")
    p = page("/tokushu-nyushi/", "analysis", "/nyushi/", "共通テストから合格発表までの流れ", "入試の日程｜共通テストから合格発表までの流れと公立高校入試", "入試の日程 共通テストから合格発表までの流れと公立高校入試",
             "大学入試と高校入試は、日程の決まり方が違います。共通テストは全国で同じ日、公立高校入試は都道府県ごとです。共通テストから合格発表までの流れと、主な8都府県の学力検査日をまとめました。",
             "大学入試と高校入試は、日程の決まり方が違います。共通テストは全国で同じ日で、公立高校入試は都道府県ごとに違います。",
             [sec(None, hero), sec(None, s_flow), sec(None, s_koko), sec(None, s_todo), sec(None, s_read), sec(None, data_blob([]))],
             [{"path": "/nyushi/", "text": "入試カレンダー（大学・高校）"}, {"path": "/kyotsu/", "text": "共通テストの日程と検定料"}, {"path": "/koko/", "text": "公立高校入試の日程（都道府県別）"}, {"path": "/zenki-koki/", "text": "国公立の前期日程と後期日程の違い"}],
             secondary=("共通テスト 日程", "公立高校入試 日程"), intent=4)
    return p


def weekday(x) -> str:
    return f"{x.year}年{x.month}月{x.day}日（{common.wd(x)}）"
