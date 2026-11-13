# 資格・試験への道(shiken-nittei.com)の作り: 2026-11-13 の差し替え後

オーナーのテンプレート(元の引き継ぎ一式は Drive の `sokuhou/inbox/shiken_デザイン差し替え_2026-11-13/`)を、リポジトリの公開の道(Python の build → sitecheck → layoutcheck → textgate → deploy)に載せた。

| 場所 | 役割 |
|---|---|
| `sites/shiken/build.py` | `node renewal/template/scripts/build-site.mjs` を呼び、問い合わせの受け口(send.php)・訪問の数え(measure.js)・Search Console の確認ファイルを足して `release/` に出す |
| `renewal/template/schedule/registry.json` | **日程の正本**(95実施回・567行)。出典 sources、確認日 checkedAt、未発表・未確認の状態を持つ |
| `renewal/template/dist/` | ブラウザで動くテンプレート(HTML/CSS/JS)。`schedule-records.js` と `expanded-catalog.js` は正本から作る生成物(`node scripts/schedule-manager.mjs build`) |
| `renewal/template/legacy/*.json` | 旧サイトの記事24本の本文。日付で変わる一覧は、ビルドの日に正本から作る |
| `renewal/template/scripts/` | schedule-core/manager/discovery/admin(日程の管理)、build-site(ページを作る)、render-pages(テンプレートを DOM で動かす)、legacy-pages(旧記事・運営者情報など)、apache-config(.htaccess)、fake-date(テスト用の日付固定) |
| `renewal/template/node_modules/` | linkedom と依存(npm なしで動くように入れてある。ISC/MIT) |
| `docs/renewal/TEMPLATE_SPEC.md` `FILE_MAP.md` | 元の仕様書とファイル構成(パスは `renewal/template/` 以下に読み替える。release-* の処理は、この構成には入れていない) |

## ビルドの日付
ページは毎回、その日の日付で作り直す(デプロイは毎朝7時にも走る)。「これから先の日程」の一覧、詳細の状態表示、カレンダーの初期表示が、その日のものになる。

## 日程を直す手順(毎朝のルーティンも同じ)
1. `python sites/shiken/tools/morning_list.py` で、確かめる公式ページの一覧を出す(正本から作る)。
2. 公式ページを開いて、日付・時刻を照らす。直す所だけ registry.json を直す(date / time / note / label / sourceId、確認日 checkedAt)。日付のない欄(未発表・未確認)に行を足さない。
3. `cd sites/shiken/renewal/template && node scripts/schedule-manager.mjs build`(共通データを作り直す)。
4. `python tests/run_tests.py --site shiken` → コミット → publish.ps1。
管理画面(`node scripts/schedule-admin.mjs`、localhost:4179)は、公式ページの変化の検出と下書き・差分に使える。履歴は `schedule/history/` に溜まる(コミットするかは、サイズを見て決める)。

## 元の引き継ぎ資料との違い
- 公開候補(`releases/<id>`)・manifest・active.json の仕組みは使っていない。公開の関門は、リポジトリの共通のもの(sitecheck、layoutcheck、textgate、本番検査とロールバック)。
- 元のテンプレートは、旧サイトの記事を「入口」だけの短いページにしていた。ここでは、旧記事の本文(日付で変わる所を外したもの)を `legacy/` に入れて引き継ぎ、一覧は正本から作る。
- 運営者情報・お問い合わせ(own form)・プライバシー・訪問の数えは、旧サイトのものを新しい見た目で引き継いだ。
