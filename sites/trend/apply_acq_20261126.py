#!/usr/bin/env python3
"""2026-11-26 daily-acquisition: two pages that get search impressions but no clicks.

* /trend-nenmatsu-chosei-shorui/ : the queries ask for 必要書類・提出期限・いつ届く・持ち物.  The title, the opening and two
  headings now use those words.  The 令和7年分 basic deduction in the comparison table was the old 48万円; the tax agency
  gives 95万円 (total income up to 132万円).
* /trend-nozomi-zensekishitei/ : the 11/21-23 period is over, so the page now answers the year-end period (12/25-1/5).
  It also said a passenger without a reserved seat cannot ride; the railway says the unreserved-seat ticket holder may
  stand in the deck of an ordinary car.

Safe to run twice."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")
DAY = "2026-11-26"

SHORUI = "trend-nenmatsu-chosei-shorui"
SHORUI_TITLE = "年末調整の必要書類は最大4枚！提出期限と証明書がいつ届くか"
SHORUI_DESC = ("年末調整の必要書類は最大4枚で、全員が出すのは2枚。提出期限の社内締切と法令上の期限、書類ごとの持ち物、"
               "証明書がいつ届くか、令和8年分で変わった数字を表でまとめました。")
SHORUI_ANSWER = ("年末調整の必要書類は最大4枚で、全員が出すのは2枚です。提出期限は勤務先の社内締切が先に来ます。"
                 "持ち物の証明書は10月上旬から届き始めます。")

NOZOMI = "trend-nozomi-zensekishitei"
NOZOMI_TITLE = "のぞみは年末年始も全席指定！12月25日〜1月5日は自由席なし"
NOZOMI_DESC = ("東海道・山陽新幹線ののぞみは、12月25日から1月5日まで全席指定席です。自由席特急券だけで乗るとどうなるか、"
               "指定席がいつ発売されるか、満席のときの探し方をまとめました。")
NOZOMI_ANSWER = ("年末年始の12月25日から1月5日は、のぞみに自由席がありません。座るには指定席が必要で、"
                 "発売は乗る日の1か月前の10時です。")
NOZOMI_LEAD = "12月25日から1月5日の「のぞみ」は全席指定。指定席は乗る日の1か月前の10時に発売です。"


def load(slug):
    return json.load(open(os.path.join(CONTENT, slug + ".json"), encoding="utf-8"))


def save(slug, d):
    with open(os.path.join(CONTENT, slug + ".json"), "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def replace_text(obj, old, new):
    """Replace `old` with `new` in every string of a JSON tree."""
    if isinstance(obj, str):
        return obj.replace(old, new)
    if isinstance(obj, list):
        return [replace_text(x, old, new) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_text(v, old, new) for k, v in obj.items()}
    return obj


def fix_shorui():
    d = load(SHORUI)
    old_answer = d["answer"]
    d.update(title=SHORUI_TITLE, h1=SHORUI_TITLE, description=SHORUI_DESC, answer=SHORUI_ANSWER,
             primary_kw="年末調整の必要書類", updated=DAY,
             secondary_kw=["年末調整 書類 提出期限", "年末調整 書類 いつ届く", "年末調整 持ち物"])
    pairs = [
        (old_answer, SHORUI_ANSWER + "会社の準備期間があるので、11月中の提出を求める勤務先が多めです。"),
        ("年末調整で提出する書類は、該当する控除の種類によって異なりますが、最大で4種類（4枚）となります。このうち、扶養家族や配偶者がいない人を含めて全員が必ず出さなければならないのは2種類です。もし提出しなかった場合、税額表の「乙欄」が適用され、本来より高い税率が引かれてしまうため注意が必要です。",
         "年末調整で出す書類は、受ける控除によって変わり、最大で4種類（4枚）です。このうち2種類は、扶養家族や配偶者がいない人も出します。扶養控除等（異動）申告書を出していないと、毎月の給与の源泉徴収に税額表の「乙欄」が使われ、高い税額が引かれるので注意しましょう。"),
        ("4枚の数え方と、自分が出す書類の確認", "年末調整の持ち物は？書類ごとに必要な証明書"),
        ("締切は2つある。会社の社内締切と、法令上の期限", "提出期限はいつまで？社内締切と法令上の期限の2つ"),
        ("未払りがあると", "未払いがあると"),
        ("48万円など（従来制度）", "95万円（合計所得金額132万円以下）"),
    ]
    # the first paragraph repeats the old opening; replace it once, not the answer field a second time
    for old, new in pairs:
        if old == old_answer and old == SHORUI_ANSWER:
            continue
        d["sections"] = replace_text(d["sections"], old, new)
    d["data_basis"] = "2026年11月26日現在"
    save(SHORUI, d)


def fix_nozomi():
    d = load(NOZOMI)
    secs = d["sections"]
    eyecatch = dict(secs[0])
    eyecatch["html"] = eyecatch["html"].replace('alt="のぞみに自由席がない日がある！11月21日からは全席指定"',
                                                'alt="のぞみに自由席がない日。乗る列車を先に決める"')
    goods = next(s for s in secs if "amazonmacs-22" in s.get("html", ""))
    tour = next(s for s in secs if "pid=892749522" in s.get("html", ""))
    new = [
        eyecatch,
        {"paras": ["結論から言うと、2026年12月25日から2027年1月5日まで、東海道・山陽新幹線の「のぞみ」は全席指定席です。いつもの自由席は、この12日間はありません。座って帰省したいなら、指定席を先に取りましょう。", "押さえるポイントは3つです。"]},
        {"html": "<ul><li>対象は、東京と博多の間を走るすべての「のぞみ」</li><li>指定席の発売は、乗る日の1か月前の同じ日の10時</li><li>自由席特急券では座れず、普通車のデッキなどの利用になる</li></ul>"},
        {"h2": "年末年始の全席指定はいつからいつまで？"},
        {"table": {"caption": "", "cols": ["項目", "内容"], "num_cols": [], "rows": [
            ["期間", "2026年12月25日（金）から2027年1月5日（火）"],
            ["対象の列車", "東海道・山陽新幹線の「のぞみ」全部（東京〜博多）"],
            ["座る方法", "指定席を予約する"]]}},
        {"paras": ["年末は25日から31日の7日間、年始は1日から5日の5日間で、合わせて12日間です。仕事納めの前後も、Uターンの時期も、まるごと重なります。11月21日から23日の3連休にも同じ扱いの期間がありましたが、こちらは終わりました。"]},
        {"h2": "自由席特急券しかないと乗れない？"},
        {"paras": ["乗ること自体はできます。鉄道会社の案内では、自由席特急券などで「のぞみ」に乗る場合は、普通車のデッキなどを利用できます。ただし座席には座れません。混み具合によっては、乗りたい列車に乗れないこともあります。", "帰省の大きな荷物を持って、何時間もデッキに立つのはなかなかの苦行です。長い区間を移動する方や、子どもと一緒の方は、指定席を取る前提で予定を組むほうが安心できます。", "もう1つ注意したいのは、この案内が「のぞみ」の話だということ。「ひかり」や「こだま」を使う場合は、その列車の座席の扱いを予約の画面で見ておきましょう。"]},
        {"h2": "指定席はいつから買える？"},
        {"paras": ["駅やインターネットの指定席は、乗る列車が出る日の1か月前（前の月の同じ日）の10時に発売です。スマートEXとエクスプレス予約は、乗る日の1年前の同じ日の5時30分から予約を受け付けています。"]},
        {"table": {"caption": "", "cols": ["乗る日", "1か月前の発売日（10時）"], "num_cols": [], "rows": [
            ["12月25日（金）", "11月25日（水）発売ずみ"],
            ["12月26日（土）", "11月26日（木）発売ずみ"],
            ["12月28日（月）", "11月28日（土）"],
            ["12月30日（水）", "11月30日（月）"],
            ["12月31日（木）・1月1日（金）", "12月1日（火）"],
            ["1月3日（日）", "12月3日（木）"],
            ["1月5日（火）", "12月5日（土）"]]}},
        {"html": '<p>12月25日から1月5日まで1日ずつの発売日は、<a href="/trend-nenmatsu-shinkansen-hatsubai-2026/">年末年始の新幹線の発売日の早見表</a>にまとめています。行きと帰りで発売日が違うので、両方メモしておきましょう。</p>'},
        {"paras": ["たとえば12月28日に帰省して1月3日に戻るなら、行きの発売は11月28日、帰りは12月3日です。往復の指定席を同じ朝にそろえることはできないので、帰りの分は5日後にもう一度取りにいくことになります。行きが取れて気が緩むと忘れがちなところです。"]},
        {"h2": "満席のときに探す順番"},
        {"html": "<ol><li>同じ日の、前後の時刻ののぞみを探す</li><li>見つからなければ「ひかり」「こだま」へ広げる</li><li>出発と到着の駅は変えず、時刻の幅をさらに広げて探す</li><li>行きが取れたら、帰りの列車もその場で押さえる</li></ol>"},
        {"paras": ["行き先を変える前に、時刻をずらすのがコツです。帰省先は動かせないので、早朝や夜の列車まで候補に入れると、選べる幅が広がります。帰りの列車を後回しにすると、Uターンの混雑にそのままぶつかります。往復はセットで取りにいきましょう。", "指定席が取れたら、列車の名前、日付、出発の時刻、乗る駅と降りる駅を、一緒に行く人にも送っておくと取り違えを防げます。"]},
        tour,
        goods,
        {"h2": "今日からできること"},
        {"html": "<ol><li>行きと帰りの乗る日を決める</li><li>それぞれの発売日を、上の表でカレンダーに入れる</li><li>第1希望と第2希望の列車を決めておく</li><li>発売ずみの日に乗る方は、今日のうちに空席を調べる</li></ol>"},
        {"paras": ["年末の移動は、席が取れた時点でひと安心。発売日の朝10時を逃さないように、アラームも仕掛けておきましょう。"]},
    ]
    new_goods = dict(goods)
    new_goods["html"] = goods["html"].replace("指定席を取ったら、移動の荷物も早めに用意しておくと、当日の乗り降りが楽になります。",
                                              "指定席が取れたら、帰省の荷物の準備も早めに始めると、当日の乗り降りが楽になります。")
    new[new.index(goods)] = new_goods
    d.update(title=NOZOMI_TITLE, h1=NOZOMI_TITLE, description=NOZOMI_DESC, answer=NOZOMI_ANSWER,
             top_lead=NOZOMI_LEAD, crumb="のぞみの全席指定", primary_kw="のぞみ", updated=DAY,
             data_basis="2026年11月26日現在", secondary_kw=["のぞみ 全席指定 年末年始", "のぞみ 自由席 いつ"],
             sections=new)
    save(NOZOMI, d)


def fix_links():
    """The related-link texts carry the article title; the release-date article repeated the wrong boarding rule."""
    titles = {"/%s/" % SHORUI: SHORUI_TITLE, "/%s/" % NOZOMI: NOZOMI_TITLE}
    for name in sorted(os.listdir(CONTENT)):
        if not name.endswith(".json"):
            continue
        slug = name[:-5]
        d = load(slug)
        before = json.dumps(d, ensure_ascii=False)
        for r in d.get("related") or []:
            if r.get("path") in titles:
                r["text"] = titles[r["path"]]
        if slug == "trend-nenmatsu-shinkansen-hatsubai-2026":
            d["sections"] = replace_text(
                d["sections"], "自由席の感覚で駅へ行っても乗れません。",
                "自由席特急券だけだと座席には座れず、普通車のデッキなどの利用になります。")
        if json.dumps(d, ensure_ascii=False) != before:
            save(slug, d)


if __name__ == "__main__":
    fix_shorui()
    fix_nozomi()
    fix_links()
    print("done")
