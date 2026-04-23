# arvex — プロジェクトルール

## 概要
学生団体向けHP制作を表に掲げた、発見→理解→提案→受注→学習の業務OSプロジェクト。
1人運営。最終目標は全自動エージェント。

## ディレクトリ構成
- `db/schema.sql` — libSQL/SQLite スキーマ定義
- `scripts/` — Python業務スクリプト（scraper, classifier, hp_generator, blob, codex_image, claude_cli, outreach, db, seed_demo）
- `web/` — 提案HP用 Next.js 16 App Router アプリ（Vercel SSR デプロイ）
- `docs/` — コンセプト・フロー設計・アーキテクチャドキュメント

## DB 操作
- DB は **Turso (libSQL)**。直接 SQL を書かず `scripts/db.py` のヘルパー経由で操作する
- `scripts/db.py` は Turso HTTP Pipeline API を httpx で叩く（`libsql-experimental` は Python 3.14 でビルドできないため不採用）
- スキーマ変更は `db/schema.sql` に反映してから `python -m scripts.db` で適用
- 提案HPの中身は `proposals.html`（完全 HTML 文書）に保存、`design_brief` と `images` は JSON

## 収益モデル
- ページ単価: 1枚目4000円 / 2枚目3000円 / 3枚目〜2000円
- 特別プラン: 15000円で10枚まで
- ドメインサブスク: 2000円/年

## 提案HP の生成（単一ターン MDX パイプライン）
- Claude 1 回の推論で `IMAGE_SPECS` JSON + MDX（画像は `{{img:ROLE}}` プレースホルダで参照）を出力
- Python が spec 通りに画像を reuse / Codex で生成 → Blob に upload → `{{img:ROLE}}` を実 URL に置換
- `{{FORM_URL}}` は outreach 送信時に form URL に置換される
- URL: `/p/[slug]` は Next.js App Router が Turso から `mdx` を読んで `next-mdx-remote/rsc` で描画
- 削除条件: 10日無返信 / 交渉失敗 / 納品済み（`proposals.status='deleted'` or `expires_at` 超過で 404）

## HP 生成の設計原則
**ゴールは「この団体のためだけに作られた HP」感の最大化**。自動化や美的完成度は手段。
- プロンプトに**メニューを供給しない**（部品列挙 / section テンプレ / concept 例 / register 例 / 禁止ジャンル名リスト）。メニューを書いた瞬間 Claude はそこから選ぶ装置になり、団体によらず同じ骨格になる
- プロンプトに書いた単語は全て **priming** になる。存在しない概念は書かない（「editorial を使うな」と書くと editorial が working memory に入る）
- Claude からデザイン判断を剥奪し、`web/components/proposal/Theme.tsx` に集約: 要素 (`h1`-`h6` / `p` / `section` / `a` / `blockquote` 等) の見た目は Theme の CSS が自動適用する。Claude は**意味論タグのみ**書く
- Theme の typography 必須キー: `h1`, `h2`, `h3`, `body-md`, `label-sm` — これを変えると要素自動スタイルが効かない
- **素材密度が理解感を作る**: scraper.py が notable_facts（人名・日付・イベント名・団体名・場所・引用句を正規表現抽出）を生成し、hp_generator が Claude に「実在候補リスト」として渡す。これに無い固有情報は書かず、削る or 抽象化する
- 画像 placeholder は**リテラル文字列の属性値だけ**（JSX テンプレートリテラル内で `${var}` と組み合わせない。Python 置換器が拾えず 404 になる）

## LLM / 画像生成は全て CLI 経由
- **Claude**: `claude -p --system-prompt ... --tools "Read" --no-session-persistence --model opus --permission-mode bypassPermissions --add-dir ...`（`scripts/claude_cli.py`）
  - Pro/Max 契約を流用するので ANTHROPIC_API_KEY は不要
  - `--bare` は使わない（API キーを要求してしまうため）
  - hp_generator は Claude に `web/components/proposal/` と一時 logo dir を Read 許可する（部品 props を実装から読む + ロゴ画像を視認するため）
- **Codex**: `codex exec -s workspace-write -c shell_environment_policy.inherit=all`（`scripts/codex_image.py`）
- **Vercel Blob**: `vercel blob put --rw-token $BLOB_READ_WRITE_TOKEN` を cwd=web/ で実行（`scripts/blob.py`）

## Instagram 取得（Playwright）
- **instagrapi は使わない**。Instagram が匿名アクセスを厳しく制限しているため、ブラウザベースが安定
- 初回実行時: `.ig_state.json` が無ければ headful Chromium で起動 → ユーザーが手動ログイン → `sessionid` cookie を polling して自動検知 → state 保存
- 2回目以降: headless で state を復元してプロフィール取得
- Claude Code の `!` 経由で `input()` を使うと EOF になるので、cookie 検知で自動化する方針

## 送付チャネル
1. Instagram DM（Playwright）
2. メール（bio からスクレイピングしたアドレス / 公式サイト）
3. 問い合わせフォーム（Playwright 補完）

## 必要な環境変数（ルート `.env` に定義、コミット禁止）
- `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` — libSQL 接続
- `OPENAI_API_KEY` — Codex 画像生成
- `BLOB_READ_WRITE_TOKEN` — Vercel Blob（`vercel env pull` で `web/.vercel/.env.pulled` に入る）
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` — メール送信
- `ARVEX_BASE_URL` — 提案HPのベースURL

**不要になったもの**
- `ANTHROPIC_API_KEY` — Claude CLI 経由のため不要
- `IG_USERNAME` / `IG_PASSWORD` — Playwright のセッションファイル `.ig_state.json` を使うため不要

Next.js は `web/next.config.ts` でルート `.env` を明示ロードしているので、`web/.env.local` は作らない。

## 禁止事項
- `.env` の読み書き・コミット不可
- `scripts/db.py` を介さない直接DB操作をスクリプトに書かない
- `.ig_state.json` / `.ig_session.json` をコミットしない
- 構造化 JSON セクション + React テンプレ描画に戻さない（カタログ埋めになる）

## デバッグ用のコツ
- Python subprocess の stdout は**バッファされて見えないことが多い** → `print(..., flush=True)` を付ける
- Codex / Claude CLI は startup で 3〜8 秒かかる → リトライより並列化の方が効く
- Claude CLI に JSON 出力させる時は、強調の `"` を `「」` に置き換えるようプロンプトで厳命
