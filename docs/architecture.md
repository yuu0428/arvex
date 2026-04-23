# arvex — 実装アーキテクチャ

## 技術スタック

| レイヤー | 採用 | 備考 |
|---|---|---|
| DB | **Turso (libSQL)** | SQLite 互換。`TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` で認証。HTTP Pipeline API で Python からも Vercel からも直接叩く |
| Python ラッパー | `scripts/db.py` | httpx で Turso HTTP API を叩くシン・ラッパー |
| Instagram 取得 | **Playwright**（headful 初回ログイン → セッション保存 → headless 取得） | `scripts/scraper.py` |
| LLM 呼び出し | **Claude Code CLI (`claude -p`)** を subprocess 経由で呼ぶ | Pro/Max 契約を流用。ANTHROPIC_API_KEY 不要 |
| 画像生成 | **Codex CLI (`codex exec`)** を subprocess 経由で呼ぶ | OpenAI の gpt-image-1 を使用。`OPENAI_API_KEY` 必要 |
| 画像ホスト | **Vercel Blob** | `vercel blob put` CLI を subprocess で叩く。URL は永続 |
| Web | **Next.js 16 App Router** | `web/app/p/[slug]/route.ts` が Route Handler で HTML を直接返す |
| ホスティング | **Vercel**（SSR） | Functions が Turso から読んで HTML を返すだけ |

## パイプライン全体像

```
[scraper.py]           Playwright で Instagram プロフィール取得
    ↓                  orgs テーブルに name / bio_summary / instagram を書き込み
[classifier.py]        claude_cli で 集客型/信用型 + 課題仮説
    ↓                  orgs を更新（category / pain_points）
[hp_generator.py]      3段階パイプライン:
    ├─ Stage 1         claude_cli で DesignBrief (JSON) を生成 → Pydantic で検証
    ├─ Stage 2         並列で Codex 画像生成 → Vercel Blob へアップロード
    └─ Stage 3         claude_cli で完全 HTML 文書を生成 → BeautifulSoup で検証
                       proposals テーブルに design_brief / images / html を保存
    ↓
[/p/<slug>]            Vercel の Route Handler が Turso から html を読んで
                       Content-Type: text/html でそのまま返す（React をバイパス）
    ↓
[outreach.py]          DM / メールで URL を送付
```

**ポイント**: 提案HP1件を追加するのに Vercel への再デプロイは不要。`hp_generator.py` が DB に書いた瞬間から `/p/<slug>` でアクセスできる。

## 設計思想: テンプレじゃなくてデザイン

旧実装（構造化 JSON セクション → React で描画）は捨てた。理由:

> 音楽サークルでも法律研究会でも、hero → features → about → stats → faq の骨格が同じになってしまい「カタログ埋め」にしかならなかった。

現行は **Claude に HTML 文書を丸ごと書かせる** 方針。各団体ごとに layout_family / typography / motif から違う。詳細は `hp_generator.py` の `BRIEF_SYSTEM_PROMPT` と `HTML_SYSTEM_PROMPT`。

## スキーマ（抜粋）

```sql
CREATE TABLE proposals (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES orgs(id),
  slug          TEXT UNIQUE NOT NULL,
  form_url      TEXT,
  design_brief  TEXT,   -- JSON: DesignBrief
  images        TEXT,   -- JSON: [{role, url, prompt, aspect_ratio, alt}]
  html          TEXT,   -- 完全な HTML 文書 <!DOCTYPE html>...</html>
  status        TEXT DEFAULT 'active',
  expires_at    TEXT,
  created_at    TEXT DEFAULT (datetime('now'))
);
```

## レンダリング（サーバ側）

`web/app/p/[slug]/route.ts` は Route Handler で、React を**一切経由せず** Turso の `html` 列をそのまま `text/html` で返す:

```ts
export async function GET(_req, { params }) {
  const { slug } = await params;
  const row = await db.execute("SELECT html, expires_at FROM proposals ...");
  if (!row?.html || expired(row)) return new Response(NOT_FOUND, { status: 404 });
  return new Response(row.html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
```

`dangerouslySetInnerHTML` でも描画は可能だが、`<html>/<head>/<body>` タグを含む完全な HTML 文書は `<div>` 内に貼ると壊れる（ブラウザが剥がす）。Route Handler で返す方式が唯一まともに動く。

## LLM 呼び出しレイヤー (`scripts/claude_cli.py`)

Pro/Max 契約を流用するため Anthropic SDK ではなく `claude` CLI を subprocess で叩く:

```
claude -p "<user_prompt>"
  --system-prompt "<system_prompt>"     # CLAUDE.md / skills 汚染を回避
  --tools ""                            # 生成中にツールを使わせない
  --no-session-persistence              # 一時的な呼び出しなので履歴不要
  --model opus
  --output-format text
```

`--bare` は使わない（ANTHROPIC_API_KEY を要求するため）。

## 画像生成レイヤー (`scripts/codex_image.py`)

Codex CLI は `-s workspace-write` で cwd 以下に書き込み可能な sandbox で起動:

```
codex exec
  -s workspace-write
  -c shell_environment_policy.inherit=all
  "Generate exactly ONE image and save it to <absolute_path> as PNG..."
```

- `hp_generator.py` は `tempfile.TemporaryDirectory()` で絶対パスを作り、Codex に書き込ませる
- 4枚前後を `ThreadPoolExecutor` で**並列生成**（実測で約1/4に短縮）

## Blob レイヤー (`scripts/blob.py`)

Vercel Blob の CLI を subprocess で叩く。ポイント:

- `cwd=web/` で実行（`.vercel/project.json` が必要）
- `--rw-token $BLOB_READ_WRITE_TOKEN` で明示トークン指定（subprocess の env 継承だけだと取れないことがあった）
- `--pathname p/<slug>/<filename>` で安定したパス
- `--force` で上書き許可
- ローカルパスは**絶対パス**で渡す（cwd=web だから相対パスは解決できない）

## 環境変数（ルート `.env`）

```
# Turso
TURSO_DATABASE_URL=libsql://arvex-...turso.io
TURSO_AUTH_TOKEN=eyJ...

# Claude CLI は OAuth セッションを使うので不要
# ANTHROPIC_API_KEY=...  ← 使わない

# Codex 画像生成用
OPENAI_API_KEY=sk-...

# Instagram は Playwright のセッション（.ig_state.json）を使うので不要
# IG_USERNAME / IG_PASSWORD ← 使わない

# メール送信
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...

# Blob（vercel env pull で取得。web/.vercel/.env.pulled にも存在）
BLOB_READ_WRITE_TOKEN=vercel_blob_rw_...
```

`scripts/db.py` がルート `.env` と `web/.vercel/.env.pulled` の両方を `load_dotenv` する。
Next.js は `web/next.config.ts` で親ディレクトリの `.env` を明示ロードする。

## 動作確認

```bash
cd /Users/yura/arvex

# DB 初期化（初回のみ）
.venv/bin/python -m scripts.db

# 実在団体で試す
.venv/bin/python -m scripts.scraper <instagram_handle>
#   → org_id を表示
.venv/bin/python -m scripts.classifier <org_id>
#   → category / pain_points を出力
.venv/bin/python -m scripts.hp_generator <org_id> <form_url>
#   → 約 4〜10分（Codex 画像生成 + Claude HTML 生成）

# 開発サーバー
cd web && npm run dev
# /p/<slug> で確認

# デプロイ
vercel deploy --prod --yes
```

## ハマったポイント（残しておく）

- **`dangerouslySetInnerHTML` は完全HTML文書を受け付けない** → Route Handler で直接返す
- **Claude に JSON 出させると日本語強調で `"` を使って壊す** → プロンプトで 「」 を強制
- **`vercel blob put` は cwd=web から、かつ `--rw-token` 明示** で安定
- **Codex の workspace-write sandbox** は cwd 直下しか書けない → 絶対パスを渡す
- **Python `input()` は Claude Code の `!` 経由だと EOF** → Playwright のログインは sessionid cookie で自動検知
- **Python 3.14 では `libsql-experimental` が wheel ビルド失敗** → Turso HTTP API を直接叩く方式に切替
- **Next.js 16 の `output: "export"` と動的ルートは両立しない** → SSR 前提で `output` 設定削除
- **親ディレクトリの `.env` を Next.js が読まない** → `next.config.ts` に `dotenv.config({ path: '../.env' })`

## 今後の拡張

- **リサーチ中に取得した画像（Instagram 投稿など）を HP に流用**し、Codex 画像は不足分だけ生成するハイブリッド方式
- **キャッシュ**: 同一 slug は Vercel Runtime Cache や `unstable_cache` で提案ごとにキャッシュ可能
- **Vercel Functions を Tokyo (hnd1) リージョンに寄せる**と Turso (ap-northeast-1) とのレイテンシが改善
- **生成結果のプレビュー → 再生成ループ** を人間が回せる管理画面
