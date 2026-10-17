# 共有辞書 lexicon(実物の言葉・型から作った辞書)— 2026-10-17

全サイト・全セッションが使う。AI が理屈で作った言い換え表ではなく、**実際に公開されている文での使われ方**を根拠にした辞書。

| ファイル | 中身 |
|---|---|
| `gift_ja.json` | ギフト(yorokobu)。人の呼び方(場面別)・贈るものの名詞・場面の言い方・『避ける言い方→実物で使う言い方』の対・見出しの型 |
| `kuma_ja.json` | クマ出没速報。目撃/出没/痕跡/人身被害、発出/発令、呼びかけの強さ、見出し・数字の書き方 |
| `saichin_ja.json` | 最低賃金速報。目安/答申/改正/改定/発効、引上げ/引き上げ、時間額/時給、金額・日付の書き方 |
| `minna_ja.json` | 素材サイト。無料/商用/クレジット/商品化/二次配布、規約・FAQの型 |
| `atomou_ja.json` | 日数・暦。あと〇日/〇日目、起算日の平たい言い方、二十四節気、日付の書き方 |
| `general_ja.json` | 全サイト共通。『AIの文に見える型』14種と、プロ・実物がその代わりにしていること(測った数字つき) |
| `sources.json` | 出典の台帳(168件)。id・URL・読めた範囲(read/partial/search-summary-only/unreadable)・確認日 |
| `proposed_examples.json` | examples.json への統合候補(自作の前後の例20件。`styleloop check` を通過済み) |
| `proposed_learned_rules.json` | learned_rules への規則の候補(見出し用。yorokobu の499見出しに当てた数つき) |

## 使い方
1. 言い直したい語・見出しを、まず `gift_ja.json` の `avoid_to_prefer` と `people` / `things_given`、または各サイトの辞書で引く。
2. 候補が複数あれば、`pick_by`(場面の選び方)と `strength` で選ぶ。**`weak` は決め手にしない**(1つの実物か、検索の要約だけ)。
3. 辞書にない語は、思いついた案を使わず、類語を3つ以上並べ、実物か検索の候補で『ふつうに使われているか』を確かめてから採用する。確かめたら、この辞書に足す(`evidence` に出典を `sources.json` に足して付ける)。
4. 判定(styleloop の Codex 判定)のプロンプトの参照資料として、`avoid_to_prefer` と `general_ja.json` の `patterns` を渡せる。

## 守っていること
- 他社の文を保存していない。入っているのは、短い語(おおむね10字まで)の使われ方、型の一般化(例は自作)、URLと確認日だけ。
- 公開リポジトリ。個人情報・秘密・訪問者のメッセージは入れない。
- 「読めなかった」を「読んだ」と書かない。読めなかったものは `sources.json` の `status: unreadable` に残す。

## 育て方
- オーナーの訂正が出たら、まず `docs/STYLE_LEARNINGS.md` の表Aに1行、`data/style/examples.json` に見本、ここに `strength: owner` で語を足す。
- 新しい実物を読んだら `sources.json` に足す。確認日が古くなった語(3か月以上)は、月1回の WEB 調査で見直す。
- `weak` の語は、2つ目の実物で確かめられたら `medium` にする。
