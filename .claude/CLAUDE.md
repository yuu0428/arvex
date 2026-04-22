# arvex — プロジェクトルール

## 概要
学生団体向けHP制作を表に掲げた、発見→理解→提案→受注→学習の業務OSプロジェクト。
1人運営。最終目標は全自動エージェント。

## ディレクトリ構成
- `db/` — SQLite スキーマ・マイグレーション（`arvex.db` は gitignore）
- `scripts/` — Python業務スクリプト（scraper, classifier, hp_generator, outreach, db）
- `web/` — 提案HP用 Next.js アプリ（Vercel デプロイ）
- `docs/` — コンセプト・フロー設計ドキュメント

## DB 操作
- 直接 SQL を書かず `scripts/db.py` のヘルパー経由で操作する
- スキーマ変更は `db/schema.sql` に反映してから `db/migrate.py` で適用

## 収益モデル
- ページ単価: 1枚目4000円 / 2枚目3000円 / 3枚目〜2000円
- 特別プラン: 15000円で10枚まで
- ドメインサブスク: 2000円/年

## 提案HP
- URL: `/p/[slug]`（パスベース、Vercel デプロイ）
- 削除条件: 10日無返信 / 交渉失敗 / 納品済み
- 生成: 原稿+コードをClaudeが生成、画像はGemini APIで生成

## 送付チャネル
1. Instagram DM（instagrapi / フォロー→DM）
2. メール（bio からスクレイピングしたアドレス）
3. 問い合わせフォーム（Playwright 補完）

## 必要な環境変数（.env に定義、コミット禁止）
- `IG_USERNAME` / `IG_PASSWORD` — Instagram（instagrapi）
- `ANTHROPIC_API_KEY` — 分類・HP生成
- `GEMINI_API_KEY` — 画像生成
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` — メール送信
- `ARVEX_BASE_URL` — 提案HPのベースURL（例: `https://arvex.jp` / 開発時は `http://localhost:3000`）

## 禁止事項
- `.env` の読み書き・コミット不可
- `arvex.db` をコミットしない
- `scripts/db.py` を介さない直接DB操作をスクリプトに書かない
- Instagram セッションファイル（`.ig_session.json`）をコミットしない
