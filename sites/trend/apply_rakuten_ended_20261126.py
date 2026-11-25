#!/usr/bin/env python3
"""2026-11-26: the Rakuten Black Friday ended on 11/25 1:59.  Turn the article, its home-page box, the related-link texts
and the "future tense" sentences in other articles into the ended form (desk request of 11/25).  Safe to run twice."""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")
NEW_TITLE = "楽天ブラックフライデーは終了しました。11月25日1時59分まででした"


def load(slug):
    return json.load(open(os.path.join(CONTENT, slug + ".json"), encoding="utf-8"))


def save(slug, d):
    p = os.path.join(CONTENT, slug + ".json")
    out = json.dumps(d, ensure_ascii=False, indent=1) + "\n"
    if out != open(p, encoding="utf-8").read():
        open(p, "w", encoding="utf-8", newline="").write(out)
        print("changed", slug)


def sub_in(obj, pairs, done):
    """replace each old text with the new one in every string of obj; `done` collects the pairs that hit"""
    if isinstance(obj, str):
        for old, new in pairs:
            if old in obj:
                obj = obj.replace(old, new)
                done.add(old)
        return obj
    if isinstance(obj, list):
        return [sub_in(x, pairs, done) for x in obj]
    if isinstance(obj, dict):
        return {k: sub_in(v, pairs, done) for k, v in obj.items()}
    return obj


def article():
    slug = "trend-rakuten-blackfriday"
    d = load(slug)
    if d["title"] == NEW_TITLE:
        return
    S = d["sections"]
    d.update({
        "updated": "2026-11-26", "data_basis": "2026年11月26日現在",
        "title": NEW_TITLE, "h1": NEW_TITLE,
        "top_lead": "ブラックフライデーのポイント還元は、11月25日1時59分で終了しました。",
        "description": "楽天市場のブラックフライデー2026は、11月25日1時59分で終了しました。付いたポイントの確かめ方と、買いまわり分の上限7,000ポイント、最大47.5倍の中身を表で振り返ります。",
        "answer": "11月25日1時59分で終了しました。買いまわり分の上限は7,000ポイントだったので、付いたポイントをマイページで確かめましょう。",
        "todo": {"deadline": "2026-11-25", "badge": "11月25日に終了", "title": "楽天ブラックフライデーは終了しました",
                 "text": "11月25日1時59分で終わりました。付いたポイントは、楽天のマイページで確かめましょう。"},
    })
    S[0]["html"] = S[0]["html"].replace("楽天市場のブラックフライデー。開催中、買いまわり分の上限は7,000ポイント",
                                        "楽天市場のブラックフライデー。買いまわり分の上限は7,000ポイントでした")
    S[1] = {"html": "<p>楽天市場のブラックフライデーは、<strong>2026年11月19日20時から11月25日1時59分まで</strong>で<strong>終了しました</strong>。"
                    "買いまわり分のポイントは、期間限定ポイントとして付きます。付与の時期と、上限7,000ポイントに達していないかは、マイページで確かめましょう。"
                    "「最大47.5倍」は、通常ポイントを含め、すべての施策を重ねた場合の最大値でした。</p>"}
    S[2] = {"paras": ["振り返っておきたいのは、次の3点です。"]}
    S[3] = {"html": "<ul><li>エントリーの受け付けは11月12日10時から11月25日1時59分まででした。期間中にエントリーしていれば、エントリー前の買い物も買いまわりの対象でした。</li>"
                    "<li>最大47.5倍は、通常ポイントを含め、すべての施策を重ねた場合の最大値で、全員に付く倍率ではありませんでした。</li>"
                    "<li>買いまわり分の獲得上限は、期間中の合計で7,000ポイントでした。ラクマ特典分の上限1,500ポイントとは別です。</li></ul>"}
    S[4] = {"paras": ["日程と受付期限は、2026年11月14日に確認した発表の内容です。終了は11月25日の公式ページでも確認しています。"]}
    S[5] = {"h2": "開催期間を振り返る"}
    S[6] = {"paras": ["楽天が11月12日に発表した開催期間と、エントリーの受付期間は次のとおりでした。"]}
    S[9] = {"html": "<p>終了は11月25日の深夜1時59分でした。次回も、<strong>日付だけでなく終了の時刻まで控えておく</strong>と、買い忘れを防げます。</p>"}
    S[10] = {"paras": ["期間中のエントリーは、買い物のあとでも対象でした。次のセールでも同じ扱いになるとは限らないので、条件は開催のたびに確認しましょう。"]}
    S[11] = {"html": S[11]["html"].replace("エントリーは、買い物の前でも途中でも構いません。先に済ませておくのが安全です。", "終了後の案内は、特集ページで確認できます。")}
    S[12] = {"h2": "最大47.5倍は全員に付いた？"}
    S[13] = {"paras": ["答えは、全員に付くわけではありませんでした。", "看板の「最大47.5倍」は、通常ポイントを含む、すべての施策を合算した最大値です。買いまわりだけで47.5倍になる、という意味でもありませんでした。"]}
    S[14] = {"html": "<p>基本の条件は、<strong>買いまわりの対象が1ショップにつき税込1,000円以上の買い物</strong>という点でした。ショップ買いまわりと楽天ラクマでの購入を合わせると最大11倍でしたが、こちらも47.5倍とは集計する範囲が違います。</p>"}
    S[19] = {"h2": "上限7,000ポイントはどう効いた？"}
    S[28] = {"paras": ["※すべて上乗せ率9％を仮定した計算例です。実際の付与率はショップ数によって変わります。",
                       "この表は、支払総額だけで実際の獲得ポイントを確定できる表ではありません。付いたポイントは、マイページの明細で確認しましょう。"]}
    S[29] = {"html": "<p>次のセールで見ておきたいのは、上限まで買える余地よりも、<strong>予定している買い物に上限がどう影響するか</strong>です。必要な物と予算を先に決めてから、ポイントを計算する順番なら、倍率につられて不要な物を足すのを防ぎやすくなります。</p>"}
    S[31] = {"paras": ["楽天関連のサービスは、日程と特典がそれぞれ違いました。楽天ブックスは市場のブラックフライデーと同じ期間で終了しましたが、楽天リーベイツは11月30日23時59分まで続きます。"]}
    S[33] = {"paras": ["楽天リーベイツのエントリー開始は、11月16日10時でした。日程と受付開始の時刻は、2026年11月14日に確認した内容です。",
                       "「最大3倍」は倍率、「最大1,000ポイント」は付与数なので、数字の大きさだけでは比べられません。リーベイツを使う場合は、期間と条件を確認しましょう。"]}
    S[34] = {"html": S[34]["html"].replace("ブックスは、期間とポイントの条件が市場とは別です。", "楽天ブックスの案内は、こちらから確認できます。")}
    S[39] = {"html": S[39]["html"].replace("Yahoo!ショッピングは11月22日の開始です。PayPayでの支払いと合わせて使いたい人は、特集の開催期間に探せば比べやすくなります。",
                                          "Yahoo!ショッピングのブラックフライデーは、11月30日1時59分まで開かれています。まだ買う物がある方は、期間中に比べてみてください。")}
    S[40] = {"html": "<p>以前の買いまわりの情報を参考にするときは、ふるさと納税の扱いにも注意が必要です。<strong>ふるさと納税は2025年10月からポイント付与も買いまわりも対象外</strong>です。次のセールで対象ショップを数えるときも、寄付はリストに含めないようにしましょう。</p>"}
    S[42] = {"html": "<ol><li><strong>付いたポイントを確かめる。</strong><br>買いまわり分は期間限定ポイントです。有効期限もあわせて確認しましょう。</li>"
                     "<li><strong>注文した商品の発送を確かめる。</strong><br>キャンセルや返品の扱いも、注文の画面で確認しましょう。</li>"
                     "<li><strong>次の買い物は、日程を見てから決める。</strong><br>定例の5と0のつく日や、12月1日のワンダフルデーがあります。楽天スーパーSALEの12月分は公式の発表前なので、発表が出てから条件を確かめましょう。</li></ol>"}
    save(slug, d)


def others():
    # the related-link texts that point at the article
    for p in glob.glob(os.path.join(CONTENT, "*.json")):
        slug = os.path.basename(p)[:-5]
        d = load(slug)
        hit = False
        for r in d.get("related", []):
            if r["path"] == "/trend-rakuten-blackfriday/" and r["text"] != NEW_TITLE:
                r["text"] = NEW_TITLE
                hit = True
        if hit:
            save(slug, d)
    pairs = {
        "trend-amazon-blackfriday-nittei": [
            ("先に始まった楽天ブラックフライデーは11月25日1時59分に終わります。", "先に始まった楽天ブラックフライデーは、11月25日1時59分に終了しました。"),
            ("Amazonより先に始まって先に終わる", "Amazonより先に始まって先に終わった"),
            ("楽天ブラックフライデーは、11月19日20時に始まっています。", "楽天ブラックフライデーは、11月19日20時に始まりました。"),
            ("楽天が11月25日1時59分に終わってから、", "楽天が11月25日1時59分に終わってから、"),
            ("楽天の終了後、約46時間の空白をはさんでAmazonが始まります。", "楽天の終了後は、約46時間の空白をはさんでAmazonが始まる日程です。"),
            ("欲しい物を「楽天の期間中に買う物」と「Amazonまで待つ物」に仕分けします。", "欲しい物を「すぐ買う物」と「Amazonまで待つ物」に仕分けします。"),
            ("楽天が終わるまでに決めたい物は、先に判断しておきましょう。", "急ぎの物は、先に判断しておきましょう。"),
            ("楽天は11月25日1時59分に終わるため、買う物は楽天とAmazonで分けて組み立てる", "楽天は11月25日に終了。これからはAmazonの日程に合わせて、買う物を決める"),
        ],
        "trend-blackfriday-hajimari-bara": [
            ("楽天市場は11月25日1時59分までと短めで、", "楽天市場は11月25日1時59分で終了し、"),
            ("楽天市場では、11月25日1時59分までにエントリーすれば、ポイントアップ期間内の購入分は、エントリー前の分も対象になると案内されています。",
             "楽天市場は11月25日1時59分に終了しました。期間中のエントリーなら、エントリー前の購入分も対象になると案内されていました。"),
        ],
    }
    for slug, pp in pairs.items():
        d = load(slug)
        done = set()
        d = sub_in(d, pp, done)
        missed = [o for o, n in pp if o not in done and n not in json.dumps(d, ensure_ascii=False)]
        assert not missed, (slug, missed)
        if done:
            d["updated"] = "2026-11-26"
            d["data_basis"] = "2026年11月26日現在"
        save(slug, d)


if __name__ == "__main__":
    article()
    others()
