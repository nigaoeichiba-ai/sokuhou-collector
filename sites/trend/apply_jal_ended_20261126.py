#!/usr/bin/env python3
"""2026-11-26: the JAL time sale ended on 11/18 but the article still said "today".  Rewrites it to the finished state (only
facts that were already in the article, confirmed 11/18) and fixes three other headlines that said today/tonight/this
weekend.  Safe to run twice."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")
TITLE = "JAL国内線タイムセールは11月18日で終了！購入した方が確認したい変更と取消の条件"


def load(slug):
    p = os.path.join(CONTENT, slug + ".json")
    return p, json.load(open(p, encoding="utf-8"))


def save(p, d):
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def jal():
    p, d = load("trend-jal-timesale-2026")
    if d["h1"] == TITLE:
        return
    s = d["sections"]
    eye, fare_table_sale, fare_table, fee_table, hotel_link = s[0], s[5], s[7], s[20], s[24]
    eye = {"html": eye["html"].replace('alt="JAL国内線タイムセール。一般販売は今日まで、予約から購入まで今日中に"',
                                       'alt="JAL国内線タイムセールの文字と旅客機のイラスト（販売中の呼びかけが入った画像。セールは11月18日で終了）"')}
    lead = ("JALの国内航空券タイムセール「JALunLun ブラックフライデーセール 2026」は、一般販売が2026年11月18日（水）23時59分までで終了しました。"
            "会員先行は11月17日、一般販売は11月18日の日程でした。購入した方は、予約の変更ができないことと、取消の手数料が時期で変わることを確認しておきましょう（条件は2026年11月18日確認）。")
    d["sections"] = [
        eye,
        {"paras": [lead, "これから旅の手配をする方は、日程と宿の取り方を先に決めると比べやすくなります。"]},
        {"html": "<ul><li>タイムセールの販売は11月17日と18日の2日間で、終了しました</li><li>搭乗期間は2027年1月4日から2月28日まで</li><li>セール運賃は予約の変更ができず、取消の手数料は出発の55日前を境に大きく変わります</li></ul>"},
        {"h2": "購入した方は変更と取消の条件を確認"},
        {"paras": ["セール運賃は「プロモーション」という運賃で、予約の変更はできません。当日に空港で空席があっても、便を変えることはできない決まりです。取り消す場合の手数料は、次の表のとおりです。"]},
        fee_table,
        {"paras": ["出発の55日前は、搭乗日ごとに違います。自分の搭乗日から日数をさかのぼって、予定を変える可能性がある方は早めに判断してください。マイルの積算率は普通席で50%です。"]},
        {"h2": "終了したセールの日程と運賃の一例"},
        {"paras": ["記録として、販売の区切りを残します。"]},
        fare_table_sale,
        {"paras": ["販売時に案内されていた運賃の一例は次のとおりです（片道の最安値、2026年11月18日確認）。いまはこの金額で買えるセールではありません。"]},
        fare_table,
        {"paras": ["この表の金額は最安値の一例で、日や便によっては設定そのものがありませんでした。運賃のほかに、対象の空港では国内線旅客施設使用料が別にかかります。乗り継ぎの離島路線も対象の一例に入っていて、羽田－鹿児島－奄美大島は15,400円から、羽田－鹿児島－屋久島は16,500円からと案内されていました。"]},
        {"h2": "ここは誤解しないで"},
        {"html": "<h3>終了後に同じ運賃で予約はできない</h3>"},
        {"paras": ["タイムセールの新規の予約は、一般販売日の11月18日23時29分で締め切られました。この記事の金額は当時の記録です。これから航空券を取る方は、その時点で表示される運賃と条件で判断してください。"]},
        {"html": "<h3>取消の手数料は一律ではない</h3>"},
        {"paras": ["出発の55日前までと、54日前から出発前までとでは、手数料の割合が大きく違います。出発後は払い戻しがありません。予定が変わりそうだと分かった時点で、搭乗日から日数を数えるのが損を小さくするコツです。"]},
        {"html": "<h3>支払い方法は当時2種類に限られていた</h3>"},
        {"paras": ["このセールはJALのWebサイトからの予約購入に限られ、支払いはクレジットカード決済とe JALポイント支払いでした。予約を入れても、その日のうちに購入まで終えない予約は取り消される決まりでした。「予約したはず」と思っている方は、購入が完了しているかを予約の確認画面で確認してください。"]},
        {"h2": "次のタイムセールに備えるなら"},
        {"paras": ["今回の条件から分かるのは、始まってから考えると間に合いにくいということです。次の機会を狙う方は、行き先と日付の候補を2つ用意し、支払いに使うクレジットカードの本人認証（3Dセキュア）を前もって確認しておくと、慌てずに済みます。", "あわせて、変更できない運賃を選んでよい旅かどうかも決めておきましょう。日付が固まっている帰省や旅行には向きますが、仕事や体調で日程が動きやすい旅は、変更できる運賃との差額を比べてから選ぶほうが安心です。次回の日程や価格は、この記事の確認日の時点では分かりません。公式の案内で確認してください。"]},
        {"h2": "宿とのセットは11月30日まで"},
        {"paras": ["航空券と宿を組み合わせるダイナミックパッケージのタイムセールは、11月30日23時57分までと案内されていました（2026年11月18日確認）。クーポンは先着順で適用条件があるので、予約の前に残りと条件を確認してください。"]},
        hotel_link,
        {"h2": "今日からできること"},
        {"html": "<ol><li>購入した方は、予約の内容と搭乗日を確認する</li><li>搭乗日の55日前の日付をメモする</li><li>旅の予定が固まっていない方は、取消の手数料を表で確認する</li><li>宿がまだの方は、泊まる日と場所を決めて料金を比べる</li></ol>"},
    ]
    d.update(title=TITLE, h1=TITLE, updated="2026-11-26", data_basis="2026年11月18日現在",
             top_lead="JAL国内線タイムセールは、11月18日23時59分で一般販売が終了しました。",
             description="JAL国内線タイムセールは11月18日で終了しました。購入した方向けに、予約の変更ができない点と取消の手数料を表でまとめています。搭乗期間は2027年1月4日から2月28日まで。",
             answer="JAL国内線のタイムセールは11月18日23時59分で終了しました。購入した方は取消の条件を確認しましょう。")
    d.pop("todo", None)
    save(p, d)
    print("changed jal")


HEADLINES = {
    "trend-switch2-eraberu-soft-set": "Switch 2「選べるソフトセット」、別々に買うより最大4,980円おトク",
    "trend-shishiza-ryuseigun-2026": "しし座流星群2026は11月17日の夜から18日の未明が見頃の予想でした",
    "trend-kouyou-miagoro-2026": "紅葉の見頃は名所でずれる！11月21日からの週末は兼六園が軸",
}


def headlines():
    for slug, h in HEADLINES.items():
        p, d = load(slug)
        if d["h1"] != h:
            d.update(title=h, h1=h, updated="2026-11-26")
            save(p, d)
            print("changed", slug)


def shishiza():
    """The meteor night is over: say so at the top and take the "tonight" wording out of the summary and the body."""
    p, d = load("trend-shishiza-ryuseigun-2026")
    note = "この観測の機会（2026年11月17日の夜から18日の明け方）は終わりました。以下は当時の見通しと準備の記録です。"
    if any(note in s.get("paras", []) for s in d["sections"]):
        return
    d.pop("todo", None)
    raw = json.dumps(d, ensure_ascii=False)
    for a, b in (("今夜17日の", "17日の"), ("今夜17日", "17日"), ("今夜から", "17日の夜から"), ("ただ今夜は", "ただ17日の夜は"),
                 ("今夜のために", "17日の夜のために"), ("今夜の", "17日の夜の"), ("今夜は", "17日の夜は"), ("今日からできること", "当時の準備の手順")):
        raw = raw.replace(a, b)
    secondary = d.get("secondary_kw")
    d = json.loads(raw)
    d["secondary_kw"] = secondary
    d["description"] = "しし座流星群2026の観測の機会は11月18日の明け方で終わりました。極大は11月18日朝9時ごろで、日本では未明が見頃という予想でした。当時の天気の見通しと準備の手順を記録として残しています。"
    d["answer"] = "しし座流星群2026の観測の機会は、11月17日の夜から18日の明け方で終わりました。"
    at = next(i for i, s in enumerate(d["sections"]) if "paras" in s)
    d["sections"].insert(at, {"paras": [note]})
    d["updated"] = "2026-11-26"
    save(p, d)
    print("changed shishiza body")


def nengajo():
    p, d = load("trend-nengajo-hayawari")
    if d["h1"] != d["title"]:
        d["h1"] = d["title"]      # links to this page carry its h1: keep the shop's name out of it
        save(p, d)
        print("changed nengajo h1")


if __name__ == "__main__":
    jal()
    headlines()
    shishiza()
    nengajo()
