# ファイルと編集箇所

## 普段編集するもの

|場所|役割・編集方針|
|---|---|
|dist/index.html|トップの枠、ヒーロー、カレンダー、共通ヘッダー・フッター。制作用noindexは公開候補生成時の処理と分ける|
|dist/styles.css、hero.css|共通デザイン、トップとヒーロー。承認済みの色と人物の切り出しを維持|
|dist/guides.js、guides.css|5つの読者別ページの文章・表示・操作|
|dist/guide-model.js|資格検索、比較、本人入力の予定メモの正規化|
|dist/exam-details.js、exam-details.css|詳細の画面構成・操作・固有メタデータ|
|dist/exam-details-data.js|元の7試験を中心とした個別の案内文|
|dist/extended-detail-copy.js|拡張した試験の説明。実施回の注記と入試向けの分岐|
|dist/detail-dates.js、schedule-ui.js、schedule.css|日程カード、期間、未発表等の表示、出典と確認日|
|dist/calendar.js|日本時間の日付、月移動、日付の抽出、保存データの読込|
|dist/app.js|トップ操作、ルーティング、保存、検索、各画面の初期化|
|dist/routes.js|通常URLと旧ハッシュURLの互換、内部リンクの正規化|
|dist/catalog.js、expanded.css|全試験の一覧、対象・公表状況・検索、ページ送り|
|dist/taxonomy.js|分野の日本語名とcategoryの共通ルール|
|dist/assets|元画像PNGと配信用WebP。使っている画像はCSS・JSも検索してから変更|
|schedule/registry.json|日程の正本。通常は管理画面か検証付きCLIで更新|
|admin/index.html、admin.js、admin.css|ローカルの管理画面|

## 生成物：直接編集しない

|場所|扱い|
|---|---|
|dist/schedule-records.js|正本から作る共通snapshot|
|dist/expanded-catalog.js|snapshotを参照する生成wrapper|
|releases/候補ID|固定された配信候補、manifest、当時の正本・ソース。編集せず新候補を作る|
|out|配信用書き出し。正本・テンプレートへ修正を戻して作り直す|
|release-state|候補と検証画面の選択、確認記録、計画。古いPCの絶対パスを設定として流用しない|

## 継続運用で使う処理

|ファイル|用途|
|---|---|
|scripts/schedule-manager.mjs|status、draft、diff、apply、check、daily、build、rollback|
|scripts/schedule-core.mjs|検証、正本と共通データ、履歴、排他制御、巡回、確認待ち|
|scripts/schedule-discovery.mjs|公式ページのリンク候補の抽出・保持|
|scripts/schedule-admin.mjs|4179のローカル管理APIと画面配信|
|scripts/release-manager.mjs|prepare、stage、verify、status、plan、export、rollback-stageなど|
|scripts/release-core.mjs|候補の生成と照合、ソースrevision、検証反映、配信計画|
|scripts/render-pages.mjs|ブラウザと同じテンプレートを静的HTMLへ生成|
|scripts/legacy-pages.mjs|旧URL対応、記事本文、関連する実施回の抽出|
|scripts/apache-config.mjs|Apache用転送・正規化・404・ヘッダーの生成|
|scripts/release-http.mjs、release-server.mjs|4180の検証配信。通常URL、旧URL、404、検索除外|
|scripts/export-xserver.mjs|確認済み候補を元の完全なリポジトリへ渡す。外部パス確認が必要|
|tests/*.test.mjs|日程、分類、表示データ、出典、巡回、通常URL、SEO、旧URL、配信物の照合|
|tests/test_release_adapter.py|本番連携アダプターの単体検査|

## 条件付きで使う検証補助

`test-existing-isolated.py`は元リポジトリがある場合の互換検査。破壊的な旧生成テストを一時フォルダーへ隔離する。Driveのルール比較1件は除外する仕組みなので、最新ルールまで確認できたとは報告しない。

`rehearse-xserver.py`は元のbuild入口からの照合。完全な元リポジトリと、そこへ書き出された確認済み候補が必要。本番へはアップロードしない。

`package-candidate.py`は2026年11月13日用の梱包補助で日付が固定。将来の配信では出力名と記録対象を見直す。

## 履歴用：通常は実行しない

以下は一度の移行・復旧・監査に使った処理。継続更新の手順ではない。

- migrate-schedule.mjs：最初の正本への移行。
- normalize-taxonomy.mjs、prepare-release-source.py：分類と通常URL等を導入した一回限りの変更。
- release-wording.py：当時の文章調整。全置換として再利用しない。
- add-release-controls.py、prepare-xserver-workflow.py：管理画面・配信設定への一回限りのパッチ。重複適用しない。
- fix-windows-export.py：当時のWindows向け修正を加えた補助。
- review-source-packets.mjs：当時の確認packetの一括反映。最新revisionへの単純な付け替えを伴うため、将来の再適用は禁止。
- check-original-generated.py：欠損した元原稿の復旧用。元の原稿を書き込むため再実行しない。
- finalize-candidate.py：特定の2候補の同一性を照合した記録作成用。古い目視済みtrueを新候補へ持ち越す用途で使わない。
- audit-release.mjs：修正前の不合格状態を調べた旧監査。現在の合否判定ツールとして使わない。
- inventory-original.py、write-schedule-audit.mjs、package-production-docs.py、build-expanded-catalog.mjs：過去の抽出・監査・梱包・互換用。用途と出力先を読んでから扱う。

## 証拠・履歴

- schedule/history、schedule/migrations：正本の前後と移行内容。古いスキーマをそのまま復元しない。
- schedule/runs、schedule/monitor.json：取得の記録。公式本文を読んだ記録とは別。
- research：調査時の資料。現在の正本より優先しない。過去の試験日をそのまま再投入しない。
- docs/release-review-20261113：修正前の判定記録。
- docs/release-candidate-20261113：修正後の判定、更新手順、テスト・目視・ビルド照合・復旧の記録。
- HERO_ASSETS.md、GUIDE_ASSETS.md等：画像・画面の制作時の背景。現行仕様はhandoffと現在のソースを参照する。

## 同梱しないもの

Git履歴、SSH鍵・認証情報、実際のCodex自動化設定、稼働中のプロセス、端末内localStorage、開発中の一時フォルダー、不要な古い候補すべて、npm本体、Python/Node本体は移管しない。依存パッケージ、lockfile、現行候補と前の候補、必要な確認資料は引き継ぎセットに含める。
