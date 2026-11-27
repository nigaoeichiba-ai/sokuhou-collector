#!/usr/bin/env python3
"""2026-11-28 (desk request): aisatsujo.com's 35% sale until 11/29 24:00, read today on its price page (30 colour sheets
4,790 yen).  The article and the simulator follow; the headline difference is now between the three companies on sale
(8,429 - 6,462 = 1,967).  Safe to run twice."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def sub(rel, pairs):
    p = os.path.join(HERE, rel)
    text = open(p, encoding="utf-8", newline="").read()
    new = text
    for old, repl in pairs:
        if repl in new:
            continue
        if old not in new:
            raise SystemExit("not found in %s: %s" % (rel, old))
        new = new.replace(old, repl)
    if new != text:
        open(p, "w", encoding="utf-8", newline="").write(new)
        print("changed", rel)


def article():
    path = os.path.join(HERE, "content", "trend-nengajo-hayawari.json")
    d = json.load(open(path, encoding="utf-8"))
    if "割引中の3社" in d["title"]:
        return
    s = d["sections"]

    def rep(text, old, new):
        assert old in text, old
        return text.replace(old, new)

    d["title"] = d["h1"] = "年賀状印刷の早割、締切は29日と30日！割引中の3社は30枚で約2,000円差"
    d["top_lead"] = "年賀状の早割は、年賀状スクエア45％OFFと挨拶状ドットコム35％OFFが29日まで、しまうまプリント12％OFFが30日まで。総額で比べましょう。"
    d["description"] = "年賀状印刷の早割は、年賀状スクエア45％OFFと挨拶状ドットコム35％OFFが11月29日まで、しまうまプリント12％OFFが30日12:59まで。30枚の総額と締切の表つき。"
    d["answer"] = ("年賀状印刷の早割は、年賀状スクエアの45％OFFが11月29日（日）23:59まで、挨拶状ドットコムの35％OFFが同じ29日の24:00まで、しまうまプリントの12％OFFが30日（月）12:59まで。"
                   "30枚・宛名印刷ありの総額は、割引中の3社のうち最安の年賀状スクエアが6,462円、挨拶状ドットコムが8,429円で、約2,000円の差です。")
    h = s[1]["html"]
    h = rep(h, "挨拶状ドットコムの40％OFFは23日（月）24:00に終わり、次の割引は公式ページで確認できていません。",
            "挨拶状ドットコムは、40％OFFが23日で終わったあと、35％OFFの特別割引が29日（日）24:00まで出ています（11月28日確認）。")
    h = rep(h, "最安の年賀状スクエア（6,462円）と、割引のない通常価格の挨拶状ドットコム（11,009円）で、約4,500円の差でした。割引が続いている年賀状スクエアとしまうまプリントだけで比べると、差は約100円です（年賀状スクエアは2026年11月28日、挨拶状ドットコムは11月24日、ほかは11月17日に各社の公式ページで確認。しまうまプリントの締切は11月28日にも確認）。",
            "割引中の3社では、最安の年賀状スクエア（6,462円）と挨拶状ドットコム（8,429円）で、約2,000円の差でした。年賀状スクエアとしまうまプリントの差は約100円です（年賀状スクエアと挨拶状ドットコムは2026年11月28日、ほかは11月17日に各社の公式ページで確認。しまうまプリントの締切は11月28日にも確認）。")
    s[1]["html"] = h
    p = s[2]["paras"][0]
    p = rep(p, "年賀状スクエアは2026年11月28日、挨拶状ドットコムは11月24日、ほかは11月17日の確認で、", "年賀状スクエアと挨拶状ドットコムは2026年11月28日、ほかは11月17日の確認で、")
    p = rep(p, "挨拶状ドットコムの40％OFFは23日で終わり、24日朝の時点で、次の割引は公式に案内されていません。", "挨拶状ドットコムは40％OFFが23日で終わり、28日の時点では35％OFFが案内されています。")
    s[2]["paras"][0] = p
    rows = [r for r in s[2]["table"]["rows"] if r[0] != "挨拶状ドットコム"]
    rows.insert(1, ["挨拶状ドットコム", "印刷料金35％OFF（特別割引）", "11月29日（日）24:00"])
    s[2]["table"]["rows"] = rows
    p = s[3]["paras"][0]
    p = rep(p, "年賀状スクエアは2026年11月28日、挨拶状ドットコムは11月24日、ほかは11月17日の確認。挨拶状ドットコムとRakpoは、割引が終わったあとの通常価格で計算しています",
            "年賀状スクエアと挨拶状ドットコムは2026年11月28日、ほかは11月17日の確認。Rakpoは、割引が終わったあとの通常価格で計算しています")
    s[3]["paras"][0] = p
    t = {r[0]: r for r in s[3]["table"]["rows"]}
    s[3]["table"]["rows"] = [t["年賀状スクエア"], t["しまうまプリント"], ["挨拶状ドットコム", "4,790円", "2,550円", "759円", "330円", "8,429円"], t["Rakpo（通常価格）"]]
    p = s[4]["paras"][0]
    p = rep(p, "挨拶状ドットコムは、割引のない通常価格で計算していて、マイページに登録してログイン注文すると送料が無料になり、総額は10,679円です。",
            "挨拶状ドットコムは35％OFF後の「デザインタイプ（カラー）」の価格です。マイページに登録してログイン注文すると送料が無料になり、総額は8,099円です。")
    s[4]["paras"][0] = p
    h = s[6]["html"]
    h = rep(h, "29日の23:59までなら年賀状スクエア、30日までならしまうまプリントが視野に入ります（挨拶状ドットコムの40％OFFは23日、Rakpoとラクスルの早割は16日で終わっています）",
            "29日までなら年賀状スクエアと挨拶状ドットコム、30日の12:59までならしまうまプリントが視野に入ります（Rakpoとラクスルの早割は16日で終わっています）")
    h = rep(h, "挨拶状ドットコムは通常価格で総額10,250円（送料無料の条件を満たせば9,920円）まで下がります",
            "挨拶状ドットコムは35％OFFの期間中、総額7,670円（送料無料の条件を満たせば7,340円）まで下がります")
    s[6]["html"] = h
    p = s[10]["paras"][0]
    p = rep(p, "料金と締切は、年賀状スクエアが2026年11月28日、挨拶状ドットコムが11月24日、ほかが11月17日に各社の公式ページで確認しました。挨拶状ドットコムの40％OFFは11月23日で終わり、総額の表では通常価格で計算しています。",
            "料金と締切は、年賀状スクエアと挨拶状ドットコムが2026年11月28日、ほかが11月17日に各社の公式ページで確認しました。挨拶状ドットコムは、総額の表で11月29日までの35％OFFの価格を使っています。")
    s[10]["paras"][0] = p
    d["credit"] = "企業の料金ページ（2026年11月28日・17日確認）、年賀はがきの発行元の発表（2026年）"
    d["todo"]["text"] = "年賀状スクエアの45％OFFと挨拶状ドットコムの35％OFFは29日まで。しまうまプリントの12％OFFは30日の12:59まで。出す枚数を数えてから注文しましょう。"
    d["todo"]["badge"] = "早割は11月29日が山場"
    open(path, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed article")


def simulator():
    sub("nengajo_sim/nengajo-sim.js", [
        ("  // Rakpo: 10〜100枚(10枚刻み)。[枚数, 定価, 55%OFF価格]\n",
         "  // 挨拶状ドットコムの35%OFF(11/28に公式で確認。11/29 24:00まで)。上の表と同じ枚数の順(デザインタイプ・カラー)\n"
         "  var AISATSU35 = [2770, 3146, 3557, 3968, 4380, 4790, 5201, 5613, 6024, 6435, 7186, 7936, 8687, 9438, 10189];\n"
         "  var AISATSU35_FROM = at(\"2026-11-28T00:00:00\"), AISATSU35_UNTIL = at(\"2026-11-30T00:00:00\");\n\n"
         "  // Rakpo: 10〜100枚(10枚刻み)。[枚数, 定価, 55%OFF価格]\n"),
        ("    s = sale(\"aisatsu\", now);\n    if (n > 100) {",
         "    var second = now >= AISATSU35_FROM && now < AISATSU35_UNTIL;\n    s = sale(\"aisatsu\", now) || second;\n    if (n > 100) {"),
        ("      out.push(row(\"aisatsu\", { onSale: s, postcard: POSTCARD * n, print: AISATSU[i][s ? 2 : 1],",
         "      var aiRow = row(\"aisatsu\", { onSale: s, postcard: POSTCARD * n, print: second ? AISATSU35[i] : AISATSU[i][s ? 2 : 1],"),
        ("          .concat(login ? [\"マイページにログインして注文する場合の送料無料で計算しています\"] : [\"送料330円で計算しています。マイページにログインして注文すると0円です\"]) }));\n",
         "          .concat(login ? [\"マイページにログインして注文する場合の送料無料で計算しています\"] : [\"送料330円で計算しています。マイページにログインして注文すると0円です\"]) });\n"
         "      if (second) { aiRow.saleLabel = \"11月29日(日)24:00\"; aiRow.saleRate = \"35%OFF\"; }\n      out.push(aiRow);\n"),
    ])
    sub("nengajo_sim/nengajo-sim.html", [
        ("確認日 年賀状スクエアは2026年11月28日、挨拶状ドットコムは2026年11月24日、ほかは11月17日(各社の金額と締切。Rakpoと挨拶状ドットコムは割引が終わったため通常価格。",
         "確認日 年賀状スクエアと挨拶状ドットコムは2026年11月28日(年賀状スクエアの45%OFFの価格は2026年11月24日にも確認)、ほかは11月17日(各社の金額と締切。Rakpoは割引が終わったため通常価格。"),
    ])


if __name__ == "__main__":
    article()
    simulator()
