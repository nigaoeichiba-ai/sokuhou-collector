# -*- coding: utf-8 -*-
"""トップページ改訂(2026-11-11)。文面は Muse(文章ツール)の確定稿 sokuhou/outbox/トップ改訂_文面確定稿_2026-11-11.md のとおり(1字も変えない)。
1) 記事タイトル13件の差し替え(題・h1・ほかの記事のリンク文を、完全一致の置き換えで揃える)。2) home.json の組み直し。"""
import html as H
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE / "content"

# ---- 1) titles (old -> new; only the ones that change)
TITLES = {
    "たまねぎは平年の55％、レタスは122％。野菜は品目ごとに献立を組む週": "たまねぎは平年の55％、レタスは122％。品目ごとに野菜の献立を組む週",
    "給与は名目4.6％増、実質2.2％増。「増えた実感がない」理由は3つある": "給与は名目4.6％増、実質は2.2％増。数字の差が家計の実感です",
    "インフルエンザは定点10.26人。増えたのは本当だが、去年よりは少ない": "インフルエンザは定点10.26人",
    "加湿器は手入れのしやすい機種を選ぶ、水は毎日入れ替える": "加湿器は手入れのしやすい機種を選ぶ",
    "年賀はがきは1枚85円。今年は日程が後ろにずれた": "年賀はがきは1枚85円",
    "防災用ライトの選び方、明るさ・電池・置き場所": "防災用ライトの選び方",
}
for f in sorted(C.glob("*.json")):
    t = f.read_text(encoding="utf-8")
    n = t
    for a, b in TITLES.items():
        n = n.replace(a, b)
    if f.name == "trend-wage-2026-09.json":
        n = n.replace('"primary_kw": "実質2.2％増"', '"primary_kw": "実質は2.2％増"')   # the keyword must stay inside the title and the h1
    if n != t:
        f.write_text(n, encoding="utf-8")

# ---- 2) the home page
def e(s):
    return H.escape(s, quote=True)


d = json.loads((C / "home.json").read_text(encoding="utf-8"))
d["updated"] = "2026-11-11"
d["data_basis"] = "2026年11月11日現在"
d["hide_children"] = True
HERO_SENTENCE = "見出しの先にある背景と数字を一次情報から読み解き、今日これから何をすればいいかまで示すサイトです。"
d["answer"] = HERO_SENTENCE      # the description stays as decided on 2026-11-10 (not in the scope of this proofreading)
d["hero"] = {"img": "/assets/img/hero-kv.webp", "width": 2384, "height": 1008,
             "alt": "黄色のサンバーストを背景に、通信衛星、動画配信のスマートフォン、ドローン、チャートと天気のピクトグラムが映る薄型モニター、ニュースアプリのタブレット、新幹線、スタジアム、上昇するグラフ、ズワイガニ、ゲーム機、取材マイク、スマートフォン、ワインが描かれたイラスト"}

LEADS = {
    "/trend-fire-prevention-week/": "コンロやストーブまわりなど、家の火の元6か所を期間中に点検する手順です",
    "/trend-fire-alarm/": "設置が進んだ次は、10年目を迎えた警報器の点検と交換が課題です",
    "/trend-rice-price/": "11週下がり続けたコメの価格が、12週ぶりに上がりました",
    "/trend-vegetable-price/": "品目ごとに平年との差が大きい週です。価格を見ながら献立を組みます",
    "/trend-wage-2026-09/": "名目と実質の差は、物価の上がり方です。数字の読み方を、家計の実感と結びつけて説明します",
    "/trend-blackfriday-price/": "割引の大きさは、通常価格と比べて初めて見えてきます",
    "/trend-influenza-44/": "定点あたりの報告数から、いまの広がり具合を追います",
    "/trend-humidifier-care/": "使い続けるには手入れの手間が決め手です。選び方をまとめています",
    "/trend-gastroenteritis-winter/": "冬に増える感染性胃腸炎の、家庭でできる対策をまとめます",
    "/trend-nengajo-print/": "年賀はがきの価格と、準備の進め方を紹介します",
    "/bousai-light/": "ランタン型とヘッドライトの、使う場面に合わせた使い分け方です",
    "/bousai-keitai-toilet/": "必要な回数の目安は、1人1日5〜6回です。使い方と処理のしかたです",
    "/bousai-denchi-juden/": "スマホを停電中も使い続けるための容量の目安と、電池のそろえ方です",
}
d["latest_leads"] = LEADS      # the order of this object is the order of the cards

FA, FP, TY = "/trend-fire-alarm/", "/trend-fire-prevention-week/", "/trend-typhoon32/"
flash = (
    '<ul class="flash">'
    f'<li><span class="fl-d">11/10</span> <a href="{FP}">秋の火災予防運動は11月15日まで｜この1週間で終わらせる、家の火の元の点検6つ</a></li>'
    f'<li><span class="fl-d">11/10</span> <span class="fl-u">更新</span> <a href="{TY}">台風32号（チャンパカ）の進路予報と、32年ぶりの発生</a></li>'
    f'<li><span class="fl-d">11/10</span> <span class="fl-u">更新</span> <a href="{FA}">住宅用火災警報器の設置率は85.5％へ上昇</a></li>'
    '</ul>'
    f'<p class="tchip"><a href="{TY}">台風32号（チャンパカ）／非常に強い・955hPa／危険度は5段階で表示（見本）｜11月10日16時現在</a></p>')

todo_items = [
    ("家の火の元を点検する", "秋の火災予防運動の期間中に、コンロやストーブまわりなど6か所を確認します。", "11月15日まで", FP),
    ("火災警報器の点検・交換を確認する", "設置率は85.5％まで上がりました。残る課題は、設置から10年目の点検と交換です。", "設置10年目が目安", FA),
    ("台風への備えを確認する", "台風32号（チャンパカ）の進路予報が出ています。水と食料、窓まわりの備えを先に確認します。", "進路予報を更新中", TY),
]
todo = '<ol class="todo">' + "".join(
    f'<li><span class="badge">{e(b)}</span><h3><a href="{h}">{e(t)}</a></h3><p>{e(p)}</p></li>' for t, p, b, h in todo_items) + "</ol>"

promises = [
    ("約束01", "「数字」の裏取りと比較", "出典がはっきりした数字と一次情報をもとに、過去のデータと比べて意味を読み解きます。", FA, "実例 住宅用火災警報器の設置率は85.5％へ上昇"),
    ("約束02", "背景と推移がわかる", "出来事に至るまでの流れと変化の過程をたどり、全体像を描きます。", TY, "実例 台風32号（チャンパカ）の進路予報と、32年ぶりの発生"),
    ("約束03", "「次に何をすべきか」がわかる", "生活や仕事への影響も踏まえて、独自の比較表や手順で次の一手まで示します。", FP, "実例 この1週間で終わらせる、家の火の元の点検6つ"),
]
prom = '<div class="feature-grid">' + "".join(
    f'<div class="fcard"><h3><small>{n}</small><br>{e(h)}</h3><p>{e(p)}</p><p class="ex"><a href="{a}">{e(t)}</a></p></div>' for n, h, p, a, t in promises) + "</div>"

# the 防災特集 panel: (name, standard sentence, link, on at the start)
ITEMS = [
    ("水", "1人1日3リットル。最低3日分、できれば1週間分", "/bousai-mizu-shokuryo/", True, "見本の備蓄量：約3.1日分"),
    ("食料", "水と同じ日数分。缶詰、レトルト、ごはん、麺類が基本", "/bousai-mizu-shokuryo/", True, ""),
    ("携帯トイレ", "1人1日5〜6回分、人数と日数分", "/bousai-keitai-toilet/", True, ""),
    ("ライト", "ランタン型とヘッドライトの使い分け", "/bousai-light/", True, ""),
    ("電池と充電器", "停電中もスマホを使い続けるためのもの。電池は同じ種類をそろえる", "/bousai-denchi-juden/", False, ""),
    ("ラジオ", "スマホの電池を使わずに情報を得る", "/bousai/", False, ""),
    ("雨具と防水仕様の靴", "両手があくレインコートと、水を通さない靴", "/bousai/", True, ""),
    ("救急用品", "けがの手当て用品と、薬・お薬手帳", "/bousai/", False, ""),
]
rows = "".join(
    f'<tr class="{"on" if on else ""}"><th scope="row"><a href="{h}">{e(n)}</a></th><td>{e(s)}' + (f'<span class="bt-sub">（補足：{e(sub)}）</span>' if sub else "") +
    f'</td><td class="bt-act"><button type="button" class="bt-btn" aria-pressed="{"true" if on else "false"}">そろっている</button></td></tr>' for n, s, h, on, sub in ITEMS)
PANEL = (
    '<div class="bt" id="bt"><p class="bt-lead">防災庁は、家庭での水と食料の備蓄について、最低3日分、できれば1週間分を備えるよう案内しています。</p>'
    '<p class="bt-desc">項目ごとに「そろっている」を押して、いまの備えの状態を確認できます。各項目の見出しは、詳しい解説ページへのリンクになっています。</p>'
    '<div class="bt-stat"><span class="bt-count"><b id="bt-n">5</b> / 8 項目</span><span class="bt-chip mid" id="bt-chip" aria-live="polite">最低限そろっている</span></div>'
    '<div class="bt-seg" id="bt-seg">' + "<div></div>" * 8 + '</div>'
    f'<div class="tablewrap bt-tw"><table class="bt-tbl"><thead><tr><th scope="col">項目</th><th scope="col">目安</th><th scope="col">チェック</th></tr></thead><tbody>{rows}</tbody></table></div>'
    '<p class="bt-note">※ チェックの選択状況が外部に送信されたり、保存されたりすることはありません。</p>'
    '<p class="more"><a href="/bousai/">防災グッズのチェックリスト、8項目で家の備えを確認しよう</a></p>'
    '''<script>
(function(){
var root=document.getElementById("bt");if(!root)return;
var btns=root.querySelectorAll(".bt-btn"),n=document.getElementById("bt-n"),chip=document.getElementById("bt-chip"),segs=root.querySelectorAll("#bt-seg div");
function label(c){return c>=8?["しっかりそろっている","high"]:c>=6?["あと少しで一通りそろう","mid"]:c===5?["最低限そろっている","mid"]:c>=3?["半分ほど。まず水と食料から","low"]:["まず水と食料から始めよう","low"];}
function update(){var c=0;btns.forEach(function(b){var on=b.getAttribute("aria-pressed")==="true";b.parentNode.parentNode.className=on?"on":"";if(on)c++;});
n.textContent=c;var l=label(c);chip.textContent=l[0];chip.className="bt-chip "+l[1];
segs.forEach(function(s,i){s.className=i<c?"on-"+l[1]:"";});}
btns.forEach(function(b){b.addEventListener("click",function(){b.setAttribute("aria-pressed",b.getAttribute("aria-pressed")==="true"?"false":"true");update();});});
update();
})();
</script></div>''')

CATS = ('<ul class="links"><li><a href="/cat/kakei/">家計・値上げ</a>：食品や光熱費の値動きと、制度の変更と、家計への影響の整理</li>'
        '<li><a href="/cat/bousai/">防災・気象</a>：台風や大雨の見通しと、家でできる備えの手順</li>'
        '<li><a href="/cat/tenki/">天気・季節</a>：気温や季節の変わり目と、体調や暮らしへの影響</li>'
        '<li><a href="/cat/kurashi/">暮らし</a>：日常の選択に直結するニュースの整理と、今すぐ試せる手順</li></ul>')

d["sections"] = [
    {"h2": "いまの速報", "html": flash},
    {"h2": "今日やること", "paras": ["ニュースを読んだら、ここから始められます。ここにあるのは、いま動いている話題に結びついた3つです。"], "html": todo},
    {"h2": "『今日の話題 速報×深掘り』3つの約束", "paras": ["約束は、言葉ではなく記事の中身で示すものです。"], "html": prom},
    {"h2": "最新の深掘り記事", "paras": ["見出しだけでは見えてこない、出来事の「その先」を解説する記事です。"], "html": "<!--TOP:latest-->"},
    {"h2": "カテゴリ", "paras": ["家計、防災、天気、暮らし。いま動いている話題を多角的に掘り下げています。"], "html": CATS},
    {"h2": "防災特集／ご自宅の備蓄・備えを8項目でチェック", "html": PANEL},
    {"h2": "取材・執筆基準", "html": "<ul><li>出典がはっきりした一次情報・公式発表をもとに調査・執筆します</li><li>事件・事故・訃報などの重い話題や、不確実なゴシップは扱いません</li><li>単なる要約にとどまらず、自作の比較表や計算・具体的な手順など、独自の視点を加えます</li></ul>"},
]
(C / "home.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("ok")
