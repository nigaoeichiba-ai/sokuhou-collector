# 公開前チェック(2026-11-17)毎日の集客ルーティン:看護師国家試験ページの title と description

## 基本情報
- 公開日: 2026-11-17
- 対象ページ: /kangoshi/(title と description だけ。本文は変えていない)
- 作業者: Claude Code(daily-acquisition)

## 1. 文章ツールのルールを使ったか
- 使ったルール: STYLE_GUIDE_JA.md。ng_rules.json はテスト(tests/test_shiken_gate.py)が走査する。
- 変更の根拠(Search Console 7日、〜11/15): 看護師国家試験の願書の語(いつから・いつまで・取り寄せ・提出日)で、順位 7.9〜19 位に表示。/kangoshi/ は 78 表示・1 クリック。

## 2. 数字・日付の突き合わせ
- 出願 11月6日〜27日・書留で消印有効・願書は10月中旬から入手できる、は、同じページの本文(厚生労働省の第116回の施行ページを 11/15 に Chrome で全文確認した内容)と同じ。新しい数字は足していない。

## 3. 機械チェック
- ソフト対象の語(人・出ます・決まります・載っています)は使っていない。

## 5. 公開の判定
- 判定: テストと NG語ゲートが通れば公開する
- tests/run_tests.py --site shiken: 984件 OK。NG語ゲート通過(0件)。

## 追記(同日2回目): /kyotsu-tsuishi/ の title・description
- 根拠(Search Console 3か月・7日): 『共通テスト 追試 会場 2027』3.7位、『共テ 追試 いつ』5.3位、『共通テスト 再試験』11位で表示があり、ページは7日で61表示・0クリック。title が既定の文だった。
- 日付: 1月23日・24日は schedule/registry.json の確認日 2026-11-13 の値と同じ。新しい数字なし。
- tests/run_tests.py --site shiken: 984件 OK。NG語0件。
