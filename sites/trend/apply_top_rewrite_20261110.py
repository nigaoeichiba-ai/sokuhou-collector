# -*- coding: utf-8 -*-
"""トップページ文案の全面差し替え(オーナー指示 2026-11-10。指示書: Drive sokuhou/inbox/トップページ文案_全面差し替え指示_2026-11-10.md と 追加指示_防災特集)。
文面は指示書の原文のまま。ヘッダー・フッターの差し替えは hooks.post に入れてある。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "content" / "home.json"
d = json.loads(p.read_text(encoding="utf-8"))

LEAD = "「今日の話題」は、ニュースの見出しや表面的な情報だけで終わりません。速報性と深い洞察を1セットにし、出来事の背景と移り変わり、数字の裏にある意味、暮らしや実務への影響、そして「次に何をすればよいか」までを、一次情報の読み直しとともに1本にまとめてお届けします。"
d["title"] = "今日の話題｜速報×深掘り"
d["h1"] = "速報ニュースを、どこよりも深掘りする。"
d["description"] = LEAD
d["answer"] = LEAD

old = {s.get("h2"): s for s in d["sections"] if s.get("h2")}
bousai = old["防災特集、家の備えを8項目で確かめる"]
bousai["h2"] = "【防災特集】ご自宅の備蓄・備えを8項目でチェック"
bousai["paras"] = [
    "防災庁から、家庭での水と食料の備蓄について「最低3日分、推奨1週間分」との呼びかけがありました。本特集では、ご家庭に必要な備えを8つの重要項目に整理し、具体的な選び方や計算の基準をまとめています。",
    "まずは下記のチェックリストでご自宅の不足分を確認し、各項目の「詳しい解説ページ」で必要な量や失敗しない選び方をご確認ください。",
    "※チェックの選択状況が外部に送信されたり、保存されたりすることはありません。安心してお使いいただけます。",
]
more = [s for s in d["sections"] if s.get("html", "").startswith('<p class="more"><a href="/bousai/">')][0]
cats_new = old["カテゴリ別の新着"]

promise = {"h2": "『今日の話題 速報×深掘り』3つの約束", "html": (
    '<div class="feature-grid">'
    '<div class="fcard"><h3><small>特徴01</small><br>「数字」の裏取りと徹底比較</h3><p>単なる噂や感情論ではなく、出典の明確な数値や一次情報をもとに分析。過去のデータと見比べることで、ニュースの本当の意味を明らかにします。</p></div>'
    '<div class="fcard"><h3><small>特徴02</small><br>背景と推移がわかる</h3><p>なぜ今この話題が注目されているのか。事象に至るまでの流れや変化のプロセスを整理し、出来事の全体像をスムーズに理解できるようにまとめます。</p></div>'
    '<div class="fcard"><h3><small>特徴03</small><br>「次に何をすべきか」がわかる実務視点</h3><p>ニュースを知ったあと、自分の生活や仕事にどう影響するのか。独自の比較表や手順を交え、読者が次にとるべき具体的なアクションまで提示します。</p></div>'
    '</div>')}
about = {"h2": "このサイトについて",
         "paras": ["「今日の話題 速報×深掘り」は、気になる速報ニュースをどこよりも深く、多角的に読み解くメディアです。事件・事故・訃報などの重い話題は扱いません。"],
         "html": '<p class="more"><a href="/about/">続きは運営者情報をご覧ください。</a></p>'}
featured = {"h2": "注目カテゴリー", "paras": ["家計、防災、天気、暮らし。いま動いている話題を多角的に掘り下げています。"], "html": (
    '<ul class="links">'
    '<li><a href="/cat/kakei/">家計・値上げ</a>：食品や光熱費の値動きと、制度の変更と、家計への影響の整理</li>'
    '<li><a href="/cat/bousai/">防災・気象</a>：台風や大雨の見通しと、家でできる備えの手順</li>'
    '<li><a href="/cat/tenki/">天気・季節</a>：気温や季節の変わり目と、体調や暮らしへの影響</li>'
    '<li><a href="/cat/kurashi/">暮らし</a>：日常の選択に直結するニュースの整理と、今すぐ試せる手順</li>'
    '</ul>')}
latest = {"h2": "最新の深掘り記事", "paras": ["見出しだけでは見えてこない、出来事の「その先」を解説した記事一覧です。"], "html": "<!--TOP:latest-->"}
policy = {"h2": "本サイトの取材・執筆基準について", "paras": ["当サイトでは、読者のみなさまに安心して確実な情報をお届けするため、以下の基準で記事を作成しています。"], "html": (
    "<ul>"
    "<li>出典の明確な一次情報・公式発表をベースに調査・執筆します。</li>"
    "<li>事件・事故・訃報などの過度に重い話題や不確実なゴシップは扱いません。</li>"
    "<li>単なる要約にとどまらず、自作の比較表や計算・具体的な手順など、独自の視点を加えて提供します。</li>"
    "</ul>")}
d["sections"] = [promise, about, featured, latest, cats_new, bousai, more, policy]
p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

s = HERE / "site.json"
t = json.loads(s.read_text(encoding="utf-8"))
a = "今の話題を、公的な発表の数字で確かめて、速く深く伝えること。"
b = "今日の話題を、ニュースの見出しだけで終わらせず、公的な発表の数字で確かめて紹介するサイトです。"
assert a in t["purpose"] and b in t["purpose"]
t["purpose"] = t["purpose"].replace(a, "今日の話題を、速く、そして深く伝えること。").replace(b, "「今日の話題 速報×深掘り」は、気になる速報ニュースをどこよりも深く、多角的に読み解くメディアです。")
s.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("ok")
