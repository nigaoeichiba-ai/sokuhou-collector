"""The detail page of 宅建 (the model of the detail pages, spec 4.2).  Blocks without data are left out; nothing is filled in by guessing."""
from __future__ import annotations

import json

from . import common, ics, ui
from .common import TODAY, d, jp, md, left, rel, ver, today_j, DESIGN_DATE, OFFICIAL_LINKS
from .model import BY_ID, events_of, pass_rate_rows, applicant_basis_rate, sit_rate, when_text, examination_events
from .pages_v2 import CHECK, POLISH, a, cal_buttons, data_blob, esc, fix, fy_label, page, sec

NEXT_YEAR_PUBLISHED = False       # 令和9年度 of 宅建: not on the organisation's page (read 2026-11-03 and again 2026-11-08)


def status(app_start: str, app_end: str, exam: str, result: str | None) -> tuple[str, str, str]:
    """(state key, the pill text, the counter's target day and words) from the dates and today (spec 5.9): never typed by hand"""
    t = TODAY
    if t < d(app_start):
        return "before", "申込前", f"申込開始まで|{app_start}"
    if t <= d(app_end):
        return "open", "申込受付中", f"申込締切まで|{app_end}"
    if t < d(exam):
        return "closed", "申込は終了しました", f"試験日まで|{exam}"
    if t == d(exam):
        return "examday", "本日が試験日です", f"試験日|{exam}"
    if result and t < d(result):
        return "waiting", "合格発表待ち", f"合格発表まで|{result}"
    return "done", "合格発表済み", ""


def takken() -> dict:
    ev = {e["id"]: e for e in events_of("takken")}
    start, mail_end, net_end, exam, res = ev["takken-start-mail"], ev["takken-deadline-mail"], ev["takken-deadline-net"], ev["takken-exam"], ev["takken-result"]
    rows5 = pass_rate_rows("takken", 5)
    cur = rows5[0]
    st_key, st_text, target = status(start["iso"], net_end["iso"], exam["iso"], res["iso"])
    gap = (d(net_end["iso"]) - d(mail_end["iso"])).days

    # 1. hero and counter
    if target:
        word, day = target.split("|")
        kind = "deadline" if word.startswith("申込締切") else "exam"
        counter = f'<div class="count"><span class="lbl">{esc(word)}</span>{ui.counter(day, kind)}<p class="when"><b>{esc(jp(day))}</b></p></div>'
    else:
        counter = '<div class="count"><span class="lbl">令和8年度の日程はすべて終わりました</span></div>'
    pills = [("done" if left(exam["iso"]) < 0 else "", f"令和8年度：試験は{'終了しました' if left(exam['iso']) < 0 else 'これからです'}"),
             ("wait", f"いまの状態：{st_text}")]
    if not NEXT_YEAR_PUBLISHED:
        pills.append(("tba", "令和9年度：日程は未発表です"))
    pills_html = '<ul class="pills">' + "".join(f'<li class="pill {c}">{esc(t)}</li>' for c, t in pills) + "</ul>"
    official = ""
    if OFFICIAL_LINKS:
        official = '<a class="btn solid" href="https://www.retio.or.jp/exam/schedule/" rel="noopener" target="_blank">公式ページで確かめる（外部サイト・不動産適正取引推進機構）</a>'
    buttons = (f'<div class="mainbtns">{official}<a class="btn solid" href="#nittei">カレンダーに入れる</a><a class="btn" href="#planner">逆算プランを作る</a>'
               f'<button type="button" class="btn js-my" data-exam="takken" data-name="宅地建物取引士（宅建）" data-url="/takken/" aria-pressed="false">マイ試験に追加</button></div>')
    steps = [("申込開始", md(start["iso"]), ""), ("郵送 締切", md(mail_end["iso"]), ""), ("ネット 締切", md(net_end["iso"]) + " " + net_end["time"], ""),
             ("試験日", md(exam["iso"]), ""), ("合格発表", md(res["iso"]), "")]
    days = [start["iso"], mail_end["iso"], net_end["iso"], exam["iso"], res["iso"]]
    now_i = next((i for i, x in enumerate(days) if d(x) >= TODAY), len(days) - 1)
    hero = (f'<p class="org">実施団体：一般財団法人 不動産適正取引推進機構（RETIO）　宅地建物取引士資格試験</p>{counter}{pills_html}{buttons}{ui.steps(steps, now_i)}<!--hero-end-->')

    # 2. dates by way of applying
    def row(label, e, tail=""):
        over = left(e["iso"]) < 0
        cal = "" if over else cal_buttons(e)
        return [label, when_text(e) + tail, "受付は終了しました" if over and "deadline" in e["id"] else ("終了しました" if over else in_days_text(e["iso"])), f'<span class="actions">{cal}</span>' if not over else cal]
    ok_rows = [
        row("郵送申込 開始", ev["takken-start-mail"]),
        row("郵送申込 締切", mail_end, "（当日消印有効）"),
        row("インターネット申込 開始", ev["takken-start-net"]),
        row("インターネット申込 締切", net_end),
        row("試験日", exam),
        row("合格発表", res, "（機構のホームページに掲示）"),
    ]
    warn = fix("宅建", "注意：郵送とネットでは締切が16日違います。令和8年度は、郵送の締切が7月15日、インターネットの締切が7月31日でした。郵送で申し込むつもりでネットの締切日を目安にすると、間に合いません。次年度も、申込方法ごとの締切を分けて確認してください。",
               f"注意：郵送とインターネットでは、締切が{gap}日違います。令和8年度の郵送の締切は{md(mail_end['iso'])}、インターネットの締切は{md(net_end['iso'])}でした。郵送で申し込む場合にインターネットの締切を目安にすると、間に合いません。次の年度も、申込の方法ごとに締切を見ておきましょう。",
               "「ネットの締切日を目安にする」の主語が抜けていた。「郵送で申し込むつもり」を「郵送で申し込む人」にして、誰の話か分かる形に。「ネット」はこのページの見出しに合わせて「インターネット」")
    fee = f'<p class="hint">受験料は8,200円（非課税）です。</p>'
    s_dates = ('<h2 id="nittei">令和8年度の日程</h2><p class="sec-sub">申込の方法によって、締切の日が違います。下の注意を先にご覧ください。</p>'
               f'<div class="warnbox"><b>{esc(warn.split("：")[0])}：</b>{esc(warn.split("：", 1)[1])}</div>'
               + ui.table(["区分", "日時", "状態", "カレンダー"], ok_rows, "宅建士試験 令和8年度の日程") + fee
               + ('<h3>令和9年度</h3><p>日程は<b>未発表</b>です。公式に発表され次第、内容を確認して掲載します。</p>' if not NEXT_YEAR_PUBLISHED else ""))

    # 3. pass rates
    bar_rows = [{"label": fy_label(r["year"]), "value": r["rate"]} for r in rows5]
    lo, hi = min(r["rate"] for r in rows5), max(r["rate"] for r in rows5)
    grows = all(rows5[i]["applicants"] > rows5[i + 1]["applicants"] and rows5[i]["examinees"] > rows5[i + 1]["examinees"] for i in range(4))
    trend = (fix("宅建", "合格率は17〜19％の範囲で動いています。申込者数と受験者数は年々増えています。計算の基準の違いは特集ページで解説しています。",
                 f"合格率は{int(lo)}〜{int(hi) + 1}％の範囲で動いています。申込者数と受験者数は、この5回で毎回増えています。計算の基準が違うと、数字の意味も変わります。特集ページに、基準の違いの解説があります。",
                 "「年々増えて」は5回分の数字で確かめられる範囲に絞り、「この5回で毎回」と言い直した") if grows else
             f"合格率は{int(lo)}〜{int(hi) + 1}％の範囲で動いています。計算の基準が違うと、数字の意味も変わります。特集ページに、基準の違いの解説があります。")
    tbl = ui.table(["年度", "申込者", "受験者", "合格者", "合格率（受験者基準）"],
                   [[fy_label(r["year"]), f'{r["applicants"]:,}', f'{r["examinees"]:,}', f'{r["passers"]:,}', f'{r["rate"]:.1f}%'] for r in rows5], "宅建士試験 直近5回の結果", num=(1, 2, 3, 4))
    s_rate = ('<h2>合格率の推移（直近5回）</h2>' f'<p class="sec-sub">{esc(trend)}</p>'
              + ui.bars(bar_rows, "宅建の合格率の推移（受験者基準・単位は％）") + '<p class="hint">棒グラフの数字は、合格率（合格者 ÷ 受験者）で、単位は％です。</p>' + tbl
              + f'<p>{fy_label(cur["year"])}の受験率は{sit_rate(cur):.1f}％でした（受験者{cur["examinees"]:,}人 ÷ 申込者{cur["applicants"]:,}人）。</p>'
              + f'<p>{a("/goukaku-ritsu/", "特集：合格率の見方を読む", "cardlink")}</p>')

    # 4. tools
    s_cost = ('<h2>総コスト計算機</h2><p class="sec-sub">受験料は固定です。テキスト代などを自分で入力すると、合計が表示されます。</p>' + ui.cost_tool(8200, "非課税")
              + '<p class="hint">' + fix("宅建", "合格したあとは、宅地建物取引士としての登録などに別途費用がかかります。この計算には含めていません。",
                                         "合格したあとの登録などの費用は、この計算に含まれていません。", "登録に費用がかかるという事実は、公式ページで確かめられなかったため、言い切らない形にした") + '</p>')
    s_plan = ('<h2 id="planner-h">逆算プランナー</h2><p class="sec-sub">' + fix("宅建", "令和9年度の日程は未発表のため、目標の日はご自身で選んでください。このサイトが勝手に日付を入れることはしません。",
                                                                              "令和9年度の日程は未発表のため、目標の日はご自身で選んでください。",
                                                                              "「勝手に」は読者への言い方としてきつい") + '</p>'
              + ui.planner_tool(None, "休日の時間を空にすると、休日は勉強しない前提で計算します。") + '<p class="hint">日程が発表されたら、試験日を目標日にして計画を立てられます。</p>')
    CHECK.append(("宅建", "逆算プランナー: 仕様書4.2は『試験日が未発表なら出さない』とあるが、素材と試作は『日付を自分で選ぶ形』で出している。利用者が日付を選ぶ形で出した"))

    # 5. eligibility: the organisation's page says nobody is excluded, so no questions are asked (spec 5.8)
    s_elig = ('<h2>受験資格</h2><p>' + fix("宅建", "宅建は、年齢・学歴・実務経験に制限がない資格です。3つの質問に答えると、そのことが確認できます。",
                                        "宅建士試験は、年齢や学歴などに関係なく、誰でも受験できます。",
                                        "素材は3問の質問で『制限がない』と確かめる作りだが、どの答えでも同じ結果になる。仕様書5.8は、制限のない試験ではチェックを置かない定め。公式の受験案内にある言い方（年齢、学歴等に関係なく）に合わせた") + '</p>'
              '<p>合格したあとの資格登録には、別に条件があります。登録の手続きは、実施団体の案内でご確認ください。</p>')
    CHECK.append(("宅建", "受験資格の記述は、2026年11月8日に機構の試験概要ページ（受験資格の欄）で確認した。『日本国内に居住する方であれば』の一文は、本文に入れていない"))

    # 6. mistakes and questions
    fails = [
        ("失敗 1", "郵送とインターネットの締切を取り違える", f"令和8年度は郵送が{md(mail_end['iso'])}、インターネットが{md(net_end['iso'])}と、締切が{gap}日違いました。郵送で出す予定でも、インターネットの締切を目安にすると、受付が終わっています。"),
        ("失敗 2", "支払い方法の決まりを見落とす",
         fix("宅建", "申込の手続きが終わっても、受験料の支払いに期限があります。支払い方法によって期限が違うため、申し込んだ画面と案内で、自分の支払い方法の期限を確認してください。",
             "インターネット申込では、クレジットカード、コンビニエンスストア、ペイジーのどれかを選んで払います。郵送申込は支払い方法が決まっていて、茨城県以外はペイジー、茨城県はコンビニです。決まった方法以外では、申込を受け付けてもらえません。",
             "素材の『支払い方法によって期限が違う』は、2026年11月8日に機構のページを読んでも確かめられなかった。確かめられた『申込の方法で支払い方法が違う』に書き換えた")),
        ("失敗 3", "会場を当日まで知らずに慌てる",
         fix("宅建", "試験会場は受験票で知らされます。受験票が届いたら、会場の場所と行き方をその日のうちに確認しておくと、当日に慌てません。",
             "試験会場は、インターネット申込ならマイページに、郵送申込なら10月初旬に発送される受験票に書かれます。会場の案内が届いたら、場所と行き方をその日のうちに確認しておくと、当日に慌てません。",
             "会場の知らされ方は申込の方法で違う。公式ページの記載に合わせた")),
    ]
    s_fail = '<h2>よくある失敗 3例</h2><div class="fail-grid">' + "".join(f'<div class="fcard"><span class="no">{n}</span><h3>{t}</h3><p>{esc(b)}</p></div>' for n, t, b in fails) + "</div>"
    faq = [
        ("令和9年度の日程はいつ発表されますか？", "現時点では未発表です。このサイトに載るのは、実施団体が公式に発表した日付だけです。発表されたら、内容を確認して掲載します。"),
        ("申込方法で締切は違いますか？", f"違います。令和8年度は、郵送が{md(mail_end['iso'])}、インターネットが{md(net_end['iso'])}{net_end['time'].replace(':', '時')}分でした。{gap}日の差があるため、申込方法を決めたら、その方法の締切を確認してください。"),
        ("令和8年度の合格発表はいつですか？",
         fix("宅建", "2026年11月25日（水）です。2026年11月8日時点であと17日です。", f"{jp(res['iso'])}の午前9時30分です。{today_j()}時点で、{rel(res['iso'])}です。機構のホームページに、合格者の受験番号などが掲示されます。",
             "発表の時刻と場所は、機構の公式ページに書かれている。読者が知りたい点を足した")),
        ("受験料はいくらですか？", fix("宅建", "8,200円（非課税）です。合格後の登録などには、別途費用がかかります。", "8,200円（非課税）です。", "登録の費用は、公式ページで確かめられなかったため外した")),
    ]
    s_faq = '<h2>よくある質問</h2><div class="faq">' + "".join(f'<details><summary>{esc(q)}</summary><p>{esc(an)}</p></details>' for q, an in faq) + "</div>"

    # 7. for those who wait for the result (only between the exam and the result)
    s_wait = ""
    if d(exam["iso"]) <= TODAY <= d(res["iso"]):
        s_wait = ('<h2>結果待ちの方へ</h2><div class="box"><h3>いまの段階は「合格発表待ち」です</h3>'
                  f'<p>令和8年度の合格発表は{esc(jp(res["iso"]))}の午前9時30分、{esc(rel(res["iso"]))}です。発表日をカレンダーに入れておくと、当日に確認を忘れません。</p>'
                  '<p>発表は、機構のホームページに、合格者の受験番号などを掲示する形で行われます。合格者には、合格証書などが簡易書留で届きます。不合格者への通知は行われません。'
                  '発表のあとの手続きは、実施団体の案内でご確認ください。</p>'
                  f'<div class="actions">{cal_buttons(res)}{a("/results/", "合格発表日の一覧へ", "btn")}</div></div>')

    # 8. exams close in field, and what to read next
    nxt = BY_ID["kanri-exam"]
    sub_fix = fix("宅建", "次に受ける人が多い資格", "宅建と分野が近い資格", "『次に受ける人が多い』は、数字の裏づけがない言い方。分野が近いことだけを述べる")
    kanri_start, kanri_end = BY_ID["kanri-start"], BY_ID["kanri-deadline"]
    s_next = (f'<h2>{sub_fix}</h2><p class="sec-sub">日程は、それぞれのページで確認できます。</p><div class="feature-grid">'
              f'<div class="fcard"><h3>管理業務主任者</h3><p>マンション管理の国家資格です。試験日は{esc(jp(nxt["iso"]))}、{esc(rel(nxt["iso"]))}です。'
              f'令和8年度の申込は、{esc(md(kanri_start["iso"]))}から{esc(md(kanri_end["iso"]))}のWeb申込でした。</p>{a("/schedule/", "日程の一覧で調べる", "cardlink")}</div>'
              f'<div class="fcard"><h3>FP技能検定</h3><p>お金に関する幅広い知識を問う検定です。FP技能検定には、不動産を扱う分野があります。</p>{a("/fp/", "FP技能検定のページを見る", "cardlink")}</div></div>')
    CHECK.append(("宅建", "素材にあった賃貸不動産経営管理士のカードは、日程と行き先のページが用意できていないため載せていない"))
    months = round((d(res["iso"]) - d(start["iso"])).days / 30.4)
    s_read = ('<h2>あわせて読む</h2><div class="feature-grid">'
              f'<div class="fcard"><h3>合格率の見方</h3><p>{cur["rate"]:.1f}％という数字が、どの人数で割って出たものかを解説します。</p>{a("/goukaku-ritsu/", "特集を読む", "cardlink")}</div>'
              f'<div class="fcard"><h3>申込の流れと、申込から合格発表までの日数</h3><p>令和8年度は、申込開始の{md(start["iso"])}から合格発表の{md(res["iso"])}まで、約{months}か月ありました。流れを追うと、次の年度の見通しが立てやすくなります。</p>{a("/flow/", "記事を読む", "cardlink")}</div>'
              f'<div class="fcard"><h3>次の試験 管理業務主任者</h3><p>試験日は{esc(md(nxt["iso"]))}、{esc(rel(nxt["iso"]))}です。</p>{a("/deadlines/", "締切の一覧で調べる", "cardlink")}</div></div>')

    ld_event = {"@context": "https://schema.org", "@type": "Event", "name": "宅地建物取引士資格試験 令和8年度", "startDate": f"{exam['iso']}T{exam['time']}:00+09:00",
                "endDate": f"{exam['iso']}T{exam['end']}:00+09:00", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
                "eventStatus": "https://schema.org/EventScheduled", "organizer": {"@type": "Organization", "name": "一般財団法人 不動産適正取引推進機構"}}
    ld_faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": an}} for q, an in faq]}
    ld_data = {"@context": "https://schema.org", "@type": "Dataset", "name": "宅建士試験の申込者・受験者・合格者・合格率（直近5回）", "description": "宅地建物取引士資格試験の直近5回の申込者数、受験者数、合格者数と、受験者基準の合格率。",
               "inLanguage": "ja", "creator": {"@type": "Organization", "name": "一般財団法人 不動産適正取引推進機構"}, "dateModified": DESIGN_DATE}
    ld = "".join('<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False).replace("</", "<\\/") + "</script>" for x in (ld_event, ld_faq, ld_data))

    answer = f"令和8年度の宅建試験は{jp(exam['iso'])}に終わり、合格発表は{md(res['iso'])}{ver(res['iso'])}。令和9年度の日程は未発表です。"
    return page(
        "/takken/", "item", "/schedule/", "宅建の試験日", "宅建の試験日・申込期間・合格発表｜令和8年度", "宅建の試験日・申込期間・合格発表 令和8年度",
        "宅地建物取引士（宅建）の令和8年度の試験日は10月18日、合格発表は11月25日です。申込期間、受験料、直近5年の合格率と、カレンダーに入れる方法、総コスト計算機、逆算プランナーをまとめました。",
        answer,
        [sec(None, hero), sec(None, s_dates), sec(None, s_rate), sec(None, s_cost), sec(None, s_plan), sec(None, s_elig), sec(None, s_fail), sec(None, s_faq),
         sec(None, s_wait) if s_wait else {}, sec(None, s_next), sec(None, s_read), sec(None, ld + data_blob([]))],
        [{"path": "/takken-junbi/", "text": "宅建は来年度に向けて、11月の今から始める準備"}, {"path": "/results/", "text": "資格試験の合格発表日の一覧"}, {"path": "/goukaku-ritsu/", "text": "合格率の見方と、資格ごとの数字"}, {"path": "/flow/", "text": "申込から合格発表までの流れ"},
         {"path": "/deadlines/", "text": "申込の締切が近い順の一覧"}], secondary=("宅建 試験日", "宅建 合格発表", "宅建 申し込み"))


def in_days_text(iso: str) -> str:
    n = left(iso)
    return "本日" if n == 0 else f"あと{n}日" if n > 0 else f"{-n}日前に終了"
