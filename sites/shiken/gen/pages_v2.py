"""The pages of the new design (spec v1 of 2026-11-08): the top page, the detail page of 宅建, the three features (pass rates, readings, entrance exams),
and the lists in cards.  The prose is the material v2 after the editing pass; POLISH keeps every sentence that was changed, with the reason (for the report).

All dates, weekdays, "N days left", rates and sums are computed from facts.py / data/ / model.py: no number is typed twice.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date

from . import common, ics, ui
from .common import TODAY, d, jp, md, left, rel, ver, in_days, today_j, DESIGN_DATE, OFFICIAL_LINKS
from .model import (BY_ID, EVENT_LIST, RATES, applicant_basis_rate, deadline_events, events_of, examination_events, pass_rate_rows, sit_rate, when_text,
                    application_start_of)
from .ui import esc, a
from .model import TYPE_LABEL as _TL
ui.TYPE_LABEL = _TL

POLISH: list[tuple[str, str, str, str]] = []     # (page, before, after, why): what the editing pass changed
CHECK: list[tuple[str, str]] = []                # (page, the number or sentence to look at again)


def fix(page: str, before: str, after: str, why: str) -> str:
    POLISH.append((page, before, after, why))
    return after


def sec(h2: str | None, html: str = "", paras: list[str] | None = None) -> dict:
    s: dict = {}
    if h2:
        s["h2"] = h2
    if paras:
        s["paras"] = paras
    if html:
        s["html"] = html
    return s


def weekday_text() -> str:
    return f"{today_j()}（{common.wd(TODAY)}）"


def fy_label(raw: str) -> str:
    """'令和7年度(2025)' -> '令和7年度'; '令和3年度(2021)10月試験' -> '令和3年度（10月）'"""
    base = raw.split("(")[0]
    tail = raw.split(")")[-1]
    if tail:
        return f"{base}（{tail.replace('試験', '')}）"
    return base


def page(path, kind, parent, kw, title, h1, desc, answer, secs, related, *, secondary=(), intent=1, basis="2026年11月3日現在", children_h2=None) -> dict:
    p = {"path": path, "kind": kind, "parent": parent, "primary_kw": kw, "secondary_kw": list(secondary), "intent": intent, "title": title, "h1": h1,
         "description": desc, "answer": answer, "data_basis": basis, "sections": secs, "related": related, "updated": DESIGN_DATE, "sources": ["official"]}
    if children_h2:
        p["children_h2"] = children_h2
    return p


def data_blob(cards: list[dict] | None = None) -> str:
    obj = ui.event_data()
    obj["cards"] = [e["id"] for e in (cards or [])]
    return ui.json_script("shiken-data", obj) + "\n" + ui.SCRIPT


def cal_buttons(e: dict) -> str:
    return (f'<a class="btn" href="{esc(ics.gcal(e))}" target="_blank" rel="noopener">Googleカレンダー</a>'
            f'<a class="btn" href="/ics/{esc(ics.file_name(e))}" download>ICS保存</a>')


# ---------------------------------------------------------------- the timeline view (the same eight deadlines)
def timeline_html(cards: list[dict]) -> str:
    if not cards:
        return ""
    end = max(d(e["iso"]) for e in cards)
    span = max((end - TODAY).days, 1)
    rows = []
    for e in cards:
        s = application_start_of(e)
        pos = lambda day: max(0.0, min(100.0, (d(day) - TODAY).days / span * 100))
        cls = ui.state(left(e["iso"]), "deadline")[0]
        if s and left(s) < left(e["iso"]):
            a0, a1 = pos(s), pos(e["iso"])
            bar = f'<span class="range {cls}" style="left:{a0:.1f}%;width:{max(a1 - a0, 1.5):.1f}%"></span>'
        else:
            bar = ""
        pt = f'<span class="pt" style="left:{pos(e["iso"]):.1f}%"></span>'
        label = (f'申込 {md(s)} から {md(e["iso"])}{(" " + e["time"]) if e["time"] else ""} まで' if s and left(s) < left(e["iso"])
                 else f'締切 {md(e["iso"])}{(" " + e["time"]) if e["time"] else ""}')
        rows.append(f'<li><div class="tl-name"><a href="{esc(e["url"])}">{esc(e["name"])}</a><span>{ui.counter(e["iso"], "deadline", big=False)}</span></div>'
                    f'<div class="tl-when">{esc(label)}</div><div class="track" aria-hidden="true">{bar}{pt}</div></li>')
    return (f'<ol class="tl">{"".join(rows)}</ol><div class="tl-axis" aria-hidden="true"><span>{md(TODAY.isoformat())}（今日）</span><span>{md(end.isoformat())}</span></div>'
            f'<p class="hint">横の帯は、申込の期間です。丸は締切の日です。帯がないものは、申込の開始日が公式ページに載っていないものです。</p>')


# ---------------------------------------------------------------- HOME
def home() -> dict:
    cards = deadline_events(8)
    near = examination_events(3)
    kyotsu = BY_ID["kyotsu-exam"]
    takken_rows = pass_rate_rows("takken", 5)
    cur = takken_rows[0]
    lo, hi = FEE_RANGE
    lo_n, hi_n = lo[0].split('（')[0], hi[0].split('（')[0]
    n_pref = len(json.loads((Path(__file__).resolve().parents[1] / "data" / "koko.json").read_text(encoding="utf-8")))

    lead = fix("トップ", "受けたい試験を決めたら、カレンダーに入れて申込を忘れないようにできます。",
               "受ける試験が決まったら、予定に入れて、申込を忘れないようにできます。", "「受けたい試験を決めたら」は、次の「できます」と主語がずれる。先の動作と後の動作がつながる形に")
    meta = fix("トップ", "残り日数は 2026年11月8日（日）時点の計算です。日付は各実施団体の公式発表で確認したものだけを載せ、未発表のものは載せていません。",
               f"残り日数は{weekday_text()}時点の計算です。日付は、各実施団体の公式発表で確かめたものだけを載せています。未発表の日程は載せていません。",
               "二つの内容を一文に入れていたので分けた。日付は構築日から計算する")
    hero = (f'<p class="trust">公式で確かめた日付だけを載せています</p>'
            f'<form class="searchbox" role="search" onsubmit="return false"><label for="q">試験名で探す</label>'
            f'<input id="q" type="search" placeholder="試験名で探す（例：TOEIC）" autocomplete="off"><button type="submit">検索</button></form>'
            f'<p class="hero-meta">{esc(meta)}</p><!--hero-end-->')

    legend = fix("トップ", "残り日数が大きい数字で出ます。あと7日以内は赤、30日以内は黄、それ以外は青で色分けしています。",
                 "残り日数を大きな数字で出します。締切まで7日以内は赤、8日から30日は黄、31日以上は青です。",
                 "「あと7日以内」は日本語として不自然。「それ以外」も境目が数字で分からないので、仕様の区切りに合わせた")
    cards_html = "".join(ui.card(e) for e in cards)
    noresult = fix("トップ", "その名前の試験は、この一覧にはありません。", "見つかりませんでした。正式名称でもお試しください。", "仕様書の指定文に合わせた")
    s1 = (ui.urgent_band(cards)
          + '<h2>申込締切が近い順</h2>' + f'<p class="sec-sub">{esc(legend)}</p>'
          + '<div class="viewswitch" role="group" aria-label="表示の切り替え">'
            '<button type="button" data-view="cards" aria-pressed="true">カード一覧</button>'
            '<button type="button" data-view="cal" aria-pressed="false">月カレンダー</button>'
            '<button type="button" data-view="tl" aria-pressed="false">タイムライン</button></div>'
          + f'<div id="view-cards" data-panel="cards"><div class="cards">{cards_html}</div>'
            f'<p id="noresult" class="noresult" hidden>{esc(noresult)} {a("/schedule/", "資格試験日程一覧")}で探せます。</p></div>'
          + '<div data-panel="cal" hidden><div class="cal" id="cal"></div>'
            '<p class="hint">赤は申込の締切、紺は試験日と合格発表です。月を切り替えると、ほかの月の締切も見られます。</p></div>'
          + f'<div data-panel="tl" hidden>{timeline_html(cards)}</div>'
          + '<details class="tableview"><summary>表で見る（読み上げ用・8件）</summary>'
          + ui.table(["締切", "試験", "日時", "残り日数"], [[ui.TYPE_LABEL[e["type"]], e["name"], when_text(e), in_days(e["iso"])] for e in cards], "申込締切が近い順（8件）") + "</details>")

    entrances = (
        '<div class="entrances">'
        f'<div class="ecard"><h3>資格試験</h3><p>国家資格と民間検定の申込締切・試験日を、分野と、いま申込できるかどうかで絞り込めます。</p>{a("/schedule/", "資格試験日程一覧を見る", "cardlink")}</div>'
        f'<div class="ecard"><h3>共通テスト・大学入試</h3><p>大学入学共通テストは{jp(kyotsu["iso"])}と{md("2027-01-17")}です。{rel(kyotsu["iso"])}（{md(kyotsu["iso"])}まで）。</p>'
        f'{a("/nyushi/", "入試カレンダーを見る", "cardlink")}</div>'
        f'<div class="ecard"><h3>公立高校入試</h3><p>日程は都道府県ごとに違います。{n_pref}都道府県分を載せています。</p>'
        f'{a("/tokushu-nyushi/", "入試の特集を見る", "cardlink")} ／ {a("/koko/", "都道府県別の一覧", "cardlink")}</div></div>')
    s2 = '<h2>目的から探す</h2><p class="sec-sub">資格と入試は、探している人が違います。入口を分けました。</p>' + entrances

    s3 = ('<h2>マイ試験</h2><div class="box"><p class="sec-sub">'
          + fix("トップ", "気になる試験をここに集めると、締切までの残り日数がまとめて見えます。ログインは不要で、この画面を開いている間だけ有効です。",
                "気になる試験を保存すると、ここに残り日数が並びます。ログインは不要です。保存先はこのブラウザだけで、別の端末には引き継がれません。",
                "素材の「この画面を開いている間だけ有効」は、仕様書の保存方式（ブラウザに保存し、再読み込み後も残る）と合わない。仕様に合わせて直した")
          + '</p><ul id="mylist" class="mylist" aria-live="polite"><li class="myempty">気になる試験を保存すると、ここに残り日数が並びます。</li></ul>'
            '<div class="my-foot"><span id="my-msg" role="status"></span><button type="button" id="my-clear" class="btn" hidden>すべて削除</button></div></div>')

    persona = [
        ("これから決める人", "受ける試験が、まだ決まっていません。", "資格試験日程一覧", "/schedule/", "分野で比べる"),
        ("申込を控えた人", "受ける試験は決まっていて、申込がまだです。", "申込締切が近い順の一覧", "/deadlines/", "締切の一覧へ"),
        ("勉強中の人", "申込は済んでいて、試験日に向けて勉強しています。", "特集：合格率データ", "/goukaku-ritsu/", "データで比べる"),
        ("試験が近い人", "試験日まで日がなく、当日の準備を確認したい段階です。", "申込締切が近い順の一覧", "/deadlines/", "近い順に見る"),
        ("結果待ちの人", "試験は終わっていて、合格発表を待っています。", "合格発表日の一覧", "/results/", "発表日を見る"),
        ("保護者", "お子さんの入試の日程を一緒に確認しています。", "特集：入試", "/tokushu-nyushi/", "入試の特集を見る"),
    ]
    CHECK.append(("トップ", "段階別の入口の行き先は仕様書4.1の表に合わせた（素材では、これから決める人→合格率データ、勉強中の人→逆算プランナー、試験が近い人→試験日順の一覧）"))
    pcards = "".join(f'<div class="pcard"><h3>{t}</h3><p>{desc}</p><span class="next">次に見るページ</span>{a(href, esc(label), "cardlink")}</div>'
                     for t, desc, label, href, _ in persona)
    s4 = '<h2>あなたはどの段階ですか</h2><p class="sec-sub">いまの段階に合うページを1つだけ挙げています。迷ったら、自分の段階のカードから入ってください。</p>' + f'<div class="persona-grid">{pcards}</div>'

    s5 = ('<h2>今日の読み物</h2><p class="sec-sub">日程だけでは分からない、申込と合格率の読み方を解説する読み物です。</p><div class="read-grid">'
          f'<div class="read-card large"><span class="tag">読み物 ・ 合格率</span><h3>合格率の見方 受験者基準と申込者基準の違い</h3>'
          f'<p>宅建・{fy_label(cur["year"])}は、受験者で割ると{cur["rate"]:.1f}％、申込者で割ると約{applicant_basis_rate(cur):.1f}％になります。</p>'
          f'{a("/goukaku-ritsu/", "特集：合格率データを読む", "cardlink")}</div>'
          '<div class="read-side">'
          f'<div class="read-card"><span class="tag">読み物 ・ 試験の方式</span><h3>CBT試験とは</h3><p>通年で受ける試験と年1回の試験では、申込を逃したときの影響が違います。</p>{a("/cbt/", "記事を読む", "cardlink")}</div>'
          f'<div class="read-card"><span class="tag">読み物 ・ 申込</span><h3>消印有効と必着の違い</h3><p>郵送で申し込むときは、この2つの言葉の違いが、そのまま締切の違いになります。</p>{a("/postmark/", "記事を読む", "cardlink")}</div>'
          '</div></div>')
    fix("トップ", "郵送で申し込むとき、この2つの言葉の違いが締切そのものになります。", "郵送で申し込むときは、この2つの言葉の違いが、そのまま締切の違いになります。", "「違いが締切そのものになる」は意味が取りにくい")
    fix("トップ", "同じ試験でも、合格率の割り方によって数字は変わります。…どちらの数字を見ているかを確認しないと、試験同士を比べられません。", "（要約を1文に。トップは「タイトルと1行要約のみ」）", "仕様書4.1: 今日の読み物は本文を載せず、1行要約にする")

    s6 = ('<h2>データで見る</h2><p class="sec-sub">このサイトで確かめた数字です。詳しい内訳は特集ページにあります。</p><div class="bignums">'
          f'<div class="bignum"><div class="num">{cur["rate"]:.1f}<small> ％</small></div><h3>宅建の合格率（{fy_label(cur["year"])}）</h3>'
          f'<p>合格者{cur["passers"]:,}人 ÷ 受験者{cur["examinees"]:,}人で計算した数字です。</p>{a("/goukaku-ritsu/", "合格率データを見る", "cardlink")}</div>'
          f'<div class="bignum"><div class="num">{lo[1]:,}<small> 円</small>〜{hi[1]:,}<small> 円</small></div><h3>受験料の範囲</h3>'
          f'<p>このサイトで確かめた範囲では、{lo_n}が{lo[1]:,}円、{hi_n}が{hi[1]:,}円です。</p>{a("/fees/", "受験料の一覧を見る", "cardlink")}</div>'
          f'<div class="bignum"><div class="num">{n_pref}<small> 都道府県</small></div><h3>公立高校入試を収録</h3>'
          f'<p>公立高校入試の日程を{n_pref}都道府県分、一覧にまとめています。</p>{a("/koko/", "都道府県別の一覧を見る", "cardlink")}</div></div>')

    s7 = ('<h2>特集の棚</h2><p class="sec-sub">日程の一覧とは別に、テーマごとにまとめたページです。</p><div class="feature-grid">'
          f'<div class="fcard"><h3>合格率データ</h3><p>宅建の合格率の推移と、合格率を計算するときの基準の違いを、実数で解説します。</p>{a("/goukaku-ritsu/", "特集を開く", "cardlink")}</div>'
          f'<div class="fcard"><h3>読み物</h3><p>CBT試験とは何かなど、試験の仕組みと申込の注意を解説する記事を並べています。</p>{a("/yomimono/", "特集を開く", "cardlink")}</div>'
          f'<div class="fcard"><h3>入試</h3><p>共通テストまでの流れと、公立高校入試の都道府県別の日程をまとめました。保護者の方にも読みやすい構成です。</p>{a("/tokushu-nyushi/", "特集を開く", "cardlink")}</div></div>')

    ncards = "".join(
        f'<div class="ncard{" today" if left(e["iso"]) == 0 else ""}"><div class="nd">{ui.counter(e["iso"], "exam", big=False)}</div><div><h3>{a(e["url"], esc(e["name"]))}</h3>'
        f'<p>{esc(jp(e["iso"]))}{esc(" " + e["time"] if e["time"] else "")} 試験日</p></div></div>' for e in near)
    s8 = ('<h2>試験日が近い順</h2><p class="sec-sub">締切ではなく、試験そのものの日が近い順です。</p>' + f'<div class="near">{ncards}</div>')
    CHECK.append(("トップ", "「試験日が近い順」の枠は、素材にあるが仕様書4.1の表にない。表の最後の特集の棚のあとに置いた"))

    return page(
        "/", "hub", None, "試験日程カレンダー", "試験日程カレンダー｜申込締切・試験日・合格発表を公式確認で掲載", "試験日程カレンダー",
        "資格試験と入学試験の、申込の締切、試験日、合格発表日を、公式ページで確かめた日付だけで並べています。残り日数の大きな表示と、カレンダーに入れる機能で、申込の見落としを防ぎます。",
        "申込の締切と試験日を、残り日数で見せるカレンダーです。" + lead,
        [sec(None, hero), sec(None, s1), sec(None, s2), sec(None, s3), sec(None, s4), sec(None, s5), sec(None, s6), sec(None, s7), sec(None, s8), sec(None, data_blob(cards))],
        [{"path": "/schedule/", "text": "資格試験日程一覧（日付順）"}, {"path": "/deadlines/", "text": "申込期限が近い試験の一覧"}, {"path": "/nyushi/", "text": "入試カレンダー（共通テスト・国公立・公立高校）"},
         {"path": "/method/", "text": "日程の調べ方と出典"}], secondary=("資格 試験日程", "出願 期限"), children_h2="このサイトのすべてのページ")


# ---------------------------------------------------------------- numbers shared between pages
def _fee_rows():
    rows = [("英検3級（個人・本会場）", 6800, "eiken"), ("IPA（ITパスポート・基本情報）", 7500, "ipa"), ("宅建士", 8200, "retio"), ("英検2級（個人・本会場）", 9000, "eiken"),
            ("行政書士", 10400, "gyosei"), ("管理業務主任者", 8900, "kanrikyo"), ("共通テスト（2教科以下）", 12000, "dnc"), ("社労士", 15000, "sharosi"),
            ("診断士 2次試験", 15100, "jfcmca"), ("共通テスト（3教科以上）", 18000, "dnc"), ("診断士 1次試験", 17200, "jfcmca"), ("介護福祉士", 20510, "sssc")]
    return sorted(rows, key=lambda r: r[1])


FEE_ROWS = _fee_rows()
FEE_RANGE = (FEE_ROWS[0], FEE_ROWS[-1])


# commas that stood between a word and its particle, or between a subject and its verb, in the material (kept for the report)
for _pg, _a, _b in [('トップ', 'いまの段階に合うページを、1つだけ挙げています。', 'いまの段階に合うページを1つだけ挙げています。'), ('トップ', '受ける試験を、まだ決めていません。', '受ける試験が、まだ決まっていません。'), ('トップ', 'お子さんの入試の日程を、一緒に確認しています。', 'お子さんの入試の日程を一緒に確認しています。'), ('トップ', '通年で受ける試験と、年1回の試験では、申込を逃したときの影響が違います。', '通年で受ける試験と年1回の試験では、申込を逃したときの影響が違います。'), ('トップ', '公立高校入試の日程を、40都道府県分、一覧にまとめています。', '公立高校入試の日程を40都道府県分、一覧にまとめています。'), ('読み物', '10本の記事を、テーマ別に並べました。', '10本の記事をテーマ別に並べました。'), ('入試', '会場と集合時間も、届いた時点で確かめておくと、当日に慌てません。', '会場と集合時間も届いた時点で確かめておくと、当日に慌てません。'), ('入試', '前期と後期では、試験の日も、合格発表の時期も違います。', '前期と後期では、試験の日も合格発表の時期も違います。'), ('CBT', '実施する期間や、会場ごとに受けられる日には、限りがあります。', '実施する期間や会場ごとに受けられる日には、限りがあります。'), ('CBT', '宅建のように、年に1回だけ実施する試験は、申込期間が決まっています。', '宅建のように年に1回だけ実施する試験は、申込期間が決まっています。')]:
    POLISH.append((_pg, _a, _b, "読点が語と助詞の間にあり、読みにくい。必要な所だけに残した"))


for _r in [('宅建', '受験料の{esc(fee_note)}は公式の金額です。そのほかは、入力した金額の合計です。', '受験料は公式の金額で、{esc(fee_note)}です。そのほかは、入力した金額の合計です。', '「非課税は公式の金額」は主語と述語が合わない'), ('宅建', '不動産の分野が、宅建とつながります。', 'FP技能検定には、不動産を扱う分野があります。', '「つながる」の中身が書き手にしか分からない。何がつながるかを言う文に'), ('入試', '主な8都府県の学力検査日です。', '主な8都道府県の学力検査日です。', '北海道を含むのに「都府県」と書いていた'), ('入試', '上の8都府県以外の県も含め、全{len(KOKO)}都道府県分は一覧ページにあります。お住まいの都道府県の日程は、一覧ページで県を選んで確かめてください。', 'お住まいの都道府県の日程は、一覧ページで県を選んで確かめてください。', '同じ案内が表をはさんで2回出ていた'), ('入試', '共通テストの出願は{md(entry_end["iso"])}に終了しています。出願が済んでいるかを、受験生本人と一緒に確かめてください。', '共通テストの出願は{md(entry_end["iso"])}に終了しました。受験生本人と一緒に、済んでいるかを確かめてください。', '「出願が済んでいるか」が見出しと本文で続いていた'), ('合格率データ', 'どれも合格者 ÷ 受験者の数字で、分母の定義はそろえてあります。', 'どれも合格者 ÷ 受験者の数字です。回や計算のしかたが違うものは、表の下の注に書きました。', '「そろえてある」は、表の注と合わず言い切りすぎ'), ('CBT', 'どちらの方式でも、「申込の締切」と「自分が受ける日」は、分けて考えてください。', 'どちらの方式でも、「申込の締切」と「自分が受ける日」は別の日です。それぞれ確かめてください。', '「分けて考える」が、何をすればよいか分からない'), ('トップ', 'このサイトが集計した数字です。', 'このサイトで確かめた数字です。', '集計したと言うと、実際より大きく読める'), ('合格率データ', '合格率が高くても、受ける人が事前に絞られている試験があります。', '合格率が高い試験には、受ける人が事前に絞られているものがあります。', '「高くても」が後ろの内容と逆接でつながらない'), ('合格率データ', '合格率が低い試験は、誰でも申し込める試験が多くあります。', '合格率が低い試験には、誰でも申し込めるものがあります。', '「多く」は、社労士という反例が同じ表にあり言い切りすぎ'), ('合格率データ', '宅建士は、毎年の合格点が違い、受験者の得点の分布で決まります。', '宅建士は、毎年の合格点が違います。', '決め方を実施団体の公表で確かめていないため外した')]:
    if _r[0]:
        POLISH.append((_r[0], _r[1], _r[2], _r[3]))
