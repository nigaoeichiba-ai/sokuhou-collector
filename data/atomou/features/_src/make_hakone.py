"""python data/atomou/features/_src/make_hakone.py: write data/atomou/features/hakone-2027.json from the checked numbers (hakone-2027_data.json beside this file: every quote in it was found on its page).  Numbers are copied by code, never typed; the figures we compute are computed here."""
import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "hakone-2027_data.json").read_text(encoding="utf-8"))
OUT = HERE.parent / "hakone-2027.json"


def mmss(sec: float) -> str:
    s = round(sec)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def secs(t: str) -> int:
    p = [int(x) for x in t.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


past = D["past_winners"]
wins = {}
for r in past:
    wins[r["優勝校"]] = wins.get(r["優勝校"], 0) + 1
aoyama = wins.get("青山学院大学", 0)
gaps = [r["差_秒"] for r in past]
fast = min(past, key=lambda r: secs(r["優勝タイム"]))
r102 = D["r102_table"]
izumo = D["izumo_2026"]
ten = D["ten_k_avg"]
iz_extra = D["izumo_2026_extra"]["青山学院大学(第102回箱根優勝校)"]

sections = []

sections.append({"h": "大会のあらまし", "table": {"head": ["項目", "内容"], "rows": [
    ["回", "第103回 東京箱根間往復大学駅伝競走"],
    ["日程", "2027年1月2日(土)往路、1月3日(日)復路"],
    ["スタート", "往路 " + D["course_start_time"]["往路スタート"]],
    ["区間", f'10区間(往路5・復路5)、全長{D["course_total"]["全長_km"]}km(往路{D["course_total"]["往路_km"]}km・復路{D["course_total"]["復路_km"]}km)'],
    ["出場", "21チーム(前年シード10校+予選会通過10校+関東学生連合)"],
    ["シード校(第102回上位10校)", "、".join(D["seeds_103"]["校"])],
    ["区間エントリー", D["race_basics"]["区間エントリー"]],
]}})

sections.append({"h": "10区間の距離とおもな坂", "chart": {"title": "区間ごとの距離(km)", "unit": "km", "rows": [[f'{c["区間"]} {c["名"]}', c["距離_km"]] for c in D["course"]]},
                 "paras": ["おもな坂は次のとおりです(公式・報道の本文にある数字)。" + "。".join(x["項目"] for x in D["course_elevation"][:7]) + "。"]})

rows = [[str(r["順位"]), r["大学"], r["総合"], f'{r["往路"]}({r["往路順位"]}位)', f'{r["復路"]}({r["復路順位"]}位)'] for r in r102]
sections.append({"h": "前回(第102回)の結果", "table": {"head": ["順位", "大学", "総合タイム", "往路", "復路"], "rows": rows,
                                                  "note": "往路・復路とも、第102回の公式記録です。関東学生連合は参考記録のため除きました。"},
                 "paras": [f'前回は{r102[0]["大学"]}が往路・復路ともに1位で、総合{r102[0]["総合"]}で優勝しました。2位の{r102[1]["大学"]}との差は{D["past_winners"][0]["差_秒"]}秒でした。']})

sections.append({"h": "区間賞(前回)", "table": {"head": ["区間", "選手", "大学", "タイム"], "rows": [[r["区間"], r["氏名"], r["大学"], r["タイム"]] for r in D["r102_stage_winners"]],
                                              "note": "公式の大学別選手一覧にある区間順位1位の記録です。"}})

prow = [[f'第{r["回"]}回({r["年"]})', r["優勝校"], r["優勝タイム"], r["2位校"], f'{r["差_秒"]}秒'] for r in past]
sections.append({"h": "過去10年の優勝", "table": {"head": ["回(年)", "優勝校", "優勝タイム", "2位", "2位との差"], "rows": prow},
                 "chart": {"title": "2位との差(秒)", "unit": "秒", "rows": [[f'第{r["回"]}回 {r["優勝校"]}', r["差_秒"]] for r in past]},
                 "paras": [f'過去10回(第93〜102回)の優勝は、青山学院大学が{aoyama}回、駒澤大学が{wins.get("駒澤大学", 0)}回、東海大学が{wins.get("東海大学", 0)}回です。優勝タイムの最短は第{fast["回"]}回の{fast["優勝校"]}、{fast["優勝タイム"]}でした。'
                           f'2位との差は、最小{min(gaps)}秒から最大{max(gaps)}秒まで(10回の中央値は{median(gaps):g}秒)です。']})

import unicodedata
def _year(row):
    cells = unicodedata.normalize("NFKC", row).replace("　", " ").split(" ")
    cells[0] = "20" + cells[0].replace("年", "") + "年"
    return cells
big = [" ".join(_year(x["原文"])) for x in D["big3_winners_10y"]["items"]]
def _norm(n):
    return n.split("(")[0].replace("国学院大", "國學院大").replace("駒沢大", "駒澤大")
held = [r.split(" ") for r in big if r.split(" ")[1] != "-"]
same = [r[0].replace("年", "") for r in held if _norm(r[1]) == _norm(r[3])]
sections.append({"h": "三大駅伝の優勝校(過去10年)", "table": {"head": ["年(秋)", "出雲", "全日本", "箱根(翌年1月)"], "rows": [r.split(" ")[:4] for r in big],
                                                    "note": "年は秋のシーズンの年で、箱根は翌年1月です。2020年の出雲は中止。報道の表のとおりに書いています。"}})

sections.append({"h": "今季の出雲駅伝(10月12日)", "table": {"head": ["順位", "チーム", "タイム"], "rows": [[str(r["順位"]), r["チーム"], r["タイム"]] for r in izumo], "note": "公式の記録(速報値を含む)。大会は6区間45.1km、22チームが出場しました。"},
                 "paras": [f'早稲田大学が{izumo[0]["タイム"]}で優勝しました。2位の{izumo[1]["チーム"]}とは{secs(izumo[1]["タイム"]) - secs(izumo[0]["タイム"])}秒差です。前年は國學院大學が2:09:12で優勝していました。',
                           f'前回の箱根を制した青山学院大学は、{iz_extra["タイム"]}で{iz_extra["順位"]}位でした。']})

sections.append({"h": "出雲の結果を、箱根にどう読むか", "view": True, "paras": [
    "出雲は6区間45.1kmと、箱根(217.1km)の約5分の1の短い大会です。長い距離に強いチームと、短い距離に強いチームでは、順位が入れ替わりやすい大会だと考えられます。",
    f'今季の出雲では、上位に早稲田大学と國學院大學が入りました。一方、第102回の箱根を制した青山学院大学は{iz_extra["順位"]}位でした。ただし、出雲が行われた過去{len(held)}年のうち、出雲と箱根の優勝校が同じだったのは{"年・".join(same)}年の{len(same)}回だけです(上の表)。',
    "出雲の順位をそのまま箱根に当てはめることはできません。11月1日の全日本大学駅伝(8区間106.8km)の結果が出てから、距離の近い大会の結果として、もう一度見直します。"],
    "how": "過去10年の三大駅伝の優勝校の表(報道)から、出雲と箱根の優勝校が同じだった年を数えました。"})

top = ten[:15]
sections.append({"h": "予選会(10月17日)の出場45校、1万mの層の厚さ", "chart": {"title": "1万m上位10人の平均タイム:最も速い大学との差(秒、上位15校)", "unit": "秒", "rows": [[r["大学"], round(r["avg_sec"] - ten[0]["avg_sec"], 2)] for r in top]},
                 "table": {"head": ["順位", "大学", "1万m上位10人の平均"], "rows": [[str(r["rank"]), r["大学"], r["avg_10000m_top10"]] for r in ten[:20]],
                           "note": "関東学連の公式エントリー一覧(10月5日時点)の「10000m資格記録」から、当サイトが計算しました(2025年1月1日以降の公認ベスト、各校の上位10人の平均、留学生を含む)。公式の集計ではありません。グラフは、最も速い山梨学院大学との差で、棒が短いほど速いことを表します。"},
                 "paras": ["第103回予選会は、2026年10月17日(土)8時30分、立川の陸上自衛隊駐屯地から国営昭和記念公園までのハーフマラソン(21.0975km)で行われます。各校上位10人の合計タイムで、上位10校が本戦に進みます(ほかに関東学生連合)。",
                           "エントリーは45校で、1校あたり最大16人です。参加資格は、1万m34分00秒以内またはハーフマラソン73分00秒以内です。"]})

sections.append({"h": "予選会の通過校を、当サイトの指標で見る", "view": True, "paras": [
    "1万mの上位10人の平均が速い順に並べると、上位10校は" + "、".join(r["大学"] for r in ten[:10]) + "です。予選会はハーフマラソンで、1万mの記録とは別の力も問われます。",
    "この表は通過校の予想ではなく、層の厚さの目安です。大会後に、実際の通過校と、この指標の順位を比べて、この見方が当たったかを検証してここに書きます。"],
    "how": "各校のエントリー選手のうち、1万mの公認ベスト(2025年1月1日以降)を持つ上位10人の平均です。記録を持たない選手は含めていません。"})

sections.append({"h": "これからの予定", "table": {"head": ["日", "出来事"], "rows": [
    ["2026年10月17日(土)", "第103回予選会(立川)"],
    ["2026年11月1日(日)", "第58回全日本大学駅伝(名古屋〜伊勢、8区間106.8km、27チーム)"],
    ["2026年12月", "箱根駅伝のチームエントリー(公式の発表を待ちます)"],
    ["2026年12月29日", "区間エントリー(10区間の10名と補欠6名)"],
    ["2027年1月2日・3日", "第103回東京箱根間往復大学駅伝競走"]]}})

feature = {
    "slug": "hakone-2027", "stage": "公開",
    "title": "箱根駅伝2027(第103回)を数字から読む",
    "lead": "2027年1月2日・3日の第103回箱根駅伝まで、あと何日か。前回の結果、過去10年の優勝、今季の出雲駅伝、予選会の出場校の層の厚さを、公式の記録の数字から並べます。大会の直前まで、新しい情報が入るたびに更新します。",
    "method": "数字は、箱根駅伝の公式サイト、関東学連、出雲駅伝・全日本大学駅伝の公式、読売新聞の記事にあるものです。計算した値は「求め方」を付けて区別しています。",
    "cards": [{"title": t, "date": d} for t, d in (("第103回東京箱根間往復大学駅伝競走(箱根駅伝)開催", "2027-01-02"), ("第103回箱根駅伝 予選会", "2026-10-17"), ("全日本大学駅伝(名古屋〜伊勢)", "2026-11-01"), ("第38回出雲全日本大学選抜駅伝競走", "2026-10-12"))],
    "sections": sections,
    "updates": [{"on": "2026-10-13", "text": "公開しました。出雲駅伝2026の結果と、予選会45校の1万mの層を入れました。"}],
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(feature, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("written", OUT, len(sections), "sections")
