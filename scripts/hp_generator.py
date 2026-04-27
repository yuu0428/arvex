"""単一推論で提案HPを生成する。

    入力 = 生の素材（bio + 投稿原文 + 関連記事 + 採取画像リスト + ブランドマーク画像）
    出力 = IMAGE_SPECS JSON + MDX（画像は `{{img:ROLE}}` プレースホルダで参照）

    Claude は 1 回の推論で両方を出し、Python が画像を生成/再利用してプレースホルダを実 URL に置換する。

    画像ワークフロー:
        Codex で並列生成 + Vercel Blob にアップロード → role → url map を作成
        MDX 内の `{{img:ROLE}}` を置換

Usage:
    python -m scripts.hp_generator <org_id> [form_url]
"""
import json
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, field_validator

from scripts import blob, claude_cli, codex_image, db, designer_registry, lp_mockup


def _download_logo(url: str, tmp_dir: Path) -> Path | None:
    """プロフィール画像（ロゴ）を temp に落とす。"""
    try:
        r = httpx.get(url, timeout=20)
        r.raise_for_status()
    except Exception:
        return None
    ext = ".jpg" if url.lower().endswith((".jpg", ".jpeg")) else ".png"
    path = tmp_dir / f"logo{ext}"
    path.write_bytes(r.content)
    return path

MODEL = "opus"
PROPOSAL_TTL_DAYS = 10

# Visual feedback loop: MDX v1 生成 → dev server で render → スクショ → Claude が vision で review → MDX v2
# ARVEX_VISUAL_REVIEW=0 で無効化。デフォルト有効（dev server 未起動時は自動でスキップ）
REVIEW_ENABLED = os.environ.get("ARVEX_VISUAL_REVIEW", "1") != "0"
DEV_SERVER_URL = os.environ.get("ARVEX_DEV_SERVER_URL", "http://localhost:3000").rstrip("/")

# Codex の画像生成 (LP mockup + 補完画像の generate) は usage limit / コスト依存があるので
# デフォルト OFF。素材写真の reuse のみで HP を構成する。
# ARVEX_ENABLE_IMAGE_GEN=1 で有効化（Codex クレジット復活時など）。
ENABLE_IMAGE_GEN = os.environ.get("ARVEX_ENABLE_IMAGE_GEN", "0") == "1"

# 公式 frontend-design skill（Anthropic, 550k+ installs）を前置して使う。
# 「generic AI aesthetics を避ける」「bold aesthetic direction を選ぶ」の設計規律を
# 公式に任せ、arvex の SYSTEM_PROMPT は「団体理解」「notable_facts」「MDX 技術制約」
# に集中させる。skill が未インストールなら prelude 無しで動く（影響は品質の微低下のみ）。
_FRONTEND_DESIGN_SKILL_PATHS = [
    Path.home() / ".claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md",
    Path.home() / ".claude/plugins/cache/claude-plugins-official/frontend-design/unknown/skills/frontend-design/SKILL.md",
]


def _load_frontend_design_prelude() -> str:
    for p in _FRONTEND_DESIGN_SKILL_PATHS:
        if p.exists():
            content = p.read_text(encoding="utf-8")
            # YAML frontmatter を剥がす
            m = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if m:
                content = content[m.end():]
            return content.strip()
    return ""


# ========================== Image spec ==========================

class ImageSpec(BaseModel):
    role: str
    source: str  # "reuse" | "generate"
    source_url: str | None = None
    prompt: str | None = None
    aspect_ratio: str
    filename: str
    alt: str

    @field_validator("aspect_ratio")
    @classmethod
    def _ratio(cls, v: str) -> str:
        if not re.fullmatch(r"\d{1,3}:\d{1,3}", v):
            raise ValueError(f"aspect_ratio must be 'W:H': got {v!r}")
        return v

    @field_validator("source")
    @classmethod
    def _source(cls, v: str) -> str:
        if v not in ("reuse", "generate"):
            raise ValueError(f"source must be 'reuse' or 'generate': {v!r}")
        return v


# ========================== Interview (agent + sub-agent) prompts ==========================

# Main agent (arvex デザイナー兼ヒアリング担当). 毎ラウンド、追加質問 or DONE 信号を出す
INTERVIEWER_SYSTEM_PROMPT = """あなたは arvex という HP 制作者のデザイナーです。
学生団体にヒアリングを行って、その団体のためだけの HP を作るための情報を引き出します。

毎ターン、下記のどちらか 1 ブロックだけを出力します:
- まだ聞くべきことがあるなら、**追加の質問 2-5 個** を QUESTIONS ブロックで
- 情報が十分なら、**DONE 信号と判断理由** を DONE ブロックで

### 質問のルール

- **具体を問う**。「貴団体の強みは？」「どんな活動をしていますか？」のような抽象的質問は禁止
- 素材から読み取れた固有情報（人名・企画名・引用・日付）に触れる質問を優先する
  - 例: 「取材記事『〇〇』が印象的でした。あの回で一番伝えたかった一言は？」
  - 例: 「『完璧じゃなくていい』はどの場面で生まれた言葉ですか？」
- HP 設計に直接効く情報を引き出す:
  1. 誰に届けたいか（相手の具体像）
  2. 読者が読み終えた時にどう感じていてほしいか
  3. この団体にしか語れないエピソードや数字
  4. ビジュアル面で大事にしたい要素 / 避けたい印象
  5. CTA の先に何が起きてほしいか
- 同じことを形を変えて聞かない（これまでの transcript を読んでから作る）

### いつ DONE にするか

- 上記 5 項目が一通り具体に把握できた
- 読者がページを読み終えた時の感情・行動が 1 文で言える
- 早すぎる DONE は禁止、浅いまま進めると HP の質が落ちる
- 逆に、情報が十分そろったら粘らずに DONE する（ループに固執しない）

### 出力形式（必ずどちらか 1 ブロックのみ。前置き / 後書き一切なし）

<!-- QUESTIONS:BEGIN -->
1. ...
2. ...
3. ...
<!-- QUESTIONS:END -->

または

<!-- DONE:BEGIN -->
- 把握できたこと: ...
- 読後感の設計: ...
- HP の方向性の核: ...
<!-- DONE:END -->
"""


# Sub-agent (団体 persona). 素材全部を持たせ、団体の立場で答える
PERSONA_SYSTEM_PROMPT_TEMPLATE = """あなたは学生団体 <{team_name}> のメンバーです。
自団体について公に知られている情報は以下の通り。これが全てで、これ以外は知らない:

=== 自団体の素材（ここから外れる事実は答えない）===

{material}

=== 素材終わり ===

arvex という HP 制作者からヒアリングを受けています。以下のルールで答えてください:

- 団体の声と語彙で答える。arvex 側の汎用語や借り物のデザイン用語を使わない
- 具体的に答える（人名・日付・数字・場所・エピソードを使える時は必ず使う）
- **素材にない事実は絶対に作らない**。分からないなら「素材にない」「ここでは答えられない」「そこはまだ決まっていない」等、正直に答える
- 質問が曖昧・不明なら聞き返しても良い
- 一問一答。簡潔に、でも中身は濃く
- 答えながら、素材から引用できる言葉 / エピソード / 数字があれば使う

### 出力形式（前置き / 後書きなし、各質問に番号付きで対応）

<!-- ANSWERS:BEGIN -->
1. ...
2. ...
3. ...
<!-- ANSWERS:END -->
"""


# ========================== Main generation prompt ==========================

SYSTEM_PROMPT = """あなたは学生団体のための home page を設計・実装するデザイナー兼エンジニアです。

素材を読んで、この団体の HP が何であるべきかを自分で言葉にし、その設計をそのまま MDX として実装します。
出力は 1 回で、IMAGE_SPECS（画像仕様 JSON）と MDX 本体の 2 つの delimiter ブロック。

### HP とは何か（機能的前提）

これは学生団体の**永続的なホームページ (Web サイト)**です。雑誌・刊行物・記事ページ・パンフレットではない。
読者は**用事があって来る**（団体の情報を探す、連絡したい、活動を見たい）。長文を鑑賞しに来ない。
HP は**リンクの doorway** — note / IG / フォーム等、実コンテンツが住む場所への道しるべ。

**機能的骨格（必須・全デザイナー共通）**:

以下の 4 構成は**必須**。装飾・順番・スタイルは自由だが、**この 4 構成のうち欠落するものがあってはならない**:

1. **Nav (固定ヘッダー)**: 画面上部に sticky/fixed で常駐。logo + 主要 anchor リンク + 主要 CTA リンク。**横並び**（縦並びは禁止）。モバイルでは hamburger or 簡略形に。
2. **Hero**: 1 画面目で「団体名 + 何をしているか 1-2 行 + **主要 CTA ボタン 1 個**」が見える。CTA は**ボタンとしての視覚 (背景色 or 強い罫線で囲み + padding + hover)**。文字リンクで終わらせない。
3. **Body セクション群** (2-5 個): 活動 / 取り組み / 参加方法 等。各 section は**視覚的に区切られている** (背景色変更、罫線、generous spacing のいずれか)。長文の流し読みではなく、**スキャナブルにブロック化**。
4. **Footer**: 画面最下部に**情報区域**として配置。SNS リンク / 連絡先 / 団体名を整理して並べる。装飾優先で情報を欠落させない。

**Web サイト UI 規約（全デザイナー共通）**:

- **CTA は必ずボタンとしての視覚を持つ**: padding + 背景色 (or 強い罫線) + hover state。「→ で誘導する文字リンク」を主要 CTA にしない（補助 CTA としてはあり）
- **Nav は横並びの bar として常時可視**。スクロールで消えない（fixed/sticky）
- **section 間の区切りが視覚的に明確**: 背景色変える、太罫線、極端な spacing のどれか。同色背景・同 spacing で延々続く長文ページ風にしない
- **Footer は明確な情報領域**として最下部にある。Nav と Footer のどちらかを欠くと「Web ページ」ではなく「文書」になる

この骨格は**雑誌でも作品でもない Web サイト**として機能するための土台。装飾・タイポグラフィ・色・モーションでデザイナーごとに大きく違う見た目になってよいが、**骨格は共通**。

### 絶対禁止事項（arvex の不可視化）

HP は**団体自身の HP**として純粋に作る。arvex は舞台裏（IG DM の文面で別途伝える）。

- ❌ 「Proposal for <団体名>」「from arvex」「提案」「arvex 編集部が…」のような arvex の自己言及・メタ情報
- ❌ 「叩き台」「ラフ」「下書き」「bulletin」「号数」「Vol.01」「Issue」「MMXXVI.IV」のような**刊行物 marker**
- ❌ 「spring 号」「4 月号」のような**一回性の時間マーカー**（HP は永続的）
- ❌ arvex のロゴ / 署名 / 連絡先 を HP 本体に入れる

HP 内で名乗るのは**団体だけ**。arvex の存在は HP からは見えない。

### 実装の自由度

MDX は React + Tailwind がそのまま動く環境です。組み方は 3 段階あり、**スタイル・装飾は自由だが、上の「機能的骨格」は欠かしてはいけない**:

1. **素の HTML + Tailwind**: `<nav>` `<section>` `<a>` `<img>` `<ul>` `<h2>` `<button>` 等を直接書ける。
   Tailwind のユーティリティクラスも任意で使える（`flex`, `grid`, `gap-8`, `text-4xl`, `rounded-full`, `bg-black`, `px-6 py-3` 等）。
   既存の Hero / Section / Card 等が合わないレイアウトは、素 HTML で組む方が自然。
2. **既存のラッパ部品**: `{components_dir}` に `Nav.tsx`, `Hero.tsx`, `Footer.tsx`, `Section.tsx`, `CTA.tsx`, `Card.tsx`, `Grid.tsx` 等のラッパがある。
   Nav / Hero / Footer / CTA は「Web サイト UI 規約」を内蔵しているので**迷ったらこれを使うと骨格が崩れにくい**。Read で props と挙動を確認できる。
3. **自作モーション**: `{components_dir}/motion/primitives.tsx` に `MotionDiv`, `MotionSection`,
   `MotionSpan`, `MotionA`, `MotionH1` 等の motion-enabled 要素がある。これらに `initial` / `animate` /
   `whileInView` / `transition` 等を自分で書いて、この団体専用のモーションを自作できる。
   例: `<MotionSection initial={{{{ opacity: 0 }}}} whileInView={{{{ opacity: 1 }}}} transition={{{{ duration: 1.2 }}}}>...</MotionSection>`
   既成の `<Reveal>` `<TextReveal>` `<Stagger>` 等も使えるが、それは参考であって正解ではない。

raw HTML で組む場合でも、**Nav / Hero (with CTA button) / 区切られた sections / Footer の 4 構成は省略禁止**。「自由 = 文書スタイルで延々と書く」ではなく「自由 = 骨格の中の見た目を自由に」。

### 守るルール

- **素材にない固有情報（人名・日付・場所・実績数字）は書かない**。代わりに:
  - その言及ごと削る
  - より抽象度の高い書き方に置き換える（例: 「[取材 01]さんとの対話回」ではなく「NPO 代表との対話回」or その記述自体を削除）
  - プレースホルダとして目立って残すくらいなら、削る / 抽象化する方が良い
- 性格付けや役割を書く時は、団体自身が使っている語を使う
- **CSS class は Tailwind ユーティリティのみ使う**。任意のセマンティック class 名（`arc-link`, `nav-desktop`, `site-hero`, `topfan-card` 等）は**禁止**。
  - 理由: arvex は **Tailwind 以外の CSS ファイルを定義していない**。任意 class 名を書くとブラウザは何も適用せず、Nav が縦並びになる / Hero が崩れる等のレイアウト破綻が起きる
  - ✅ `<a className="text-sm hover:opacity-70 transition">取材姿勢</a>`
  - ✅ `<ul className="hidden md:flex gap-8">...</ul>`
  - ❌ `<a className="arc-link">取材姿勢</a>`（`arc-link` という CSS は存在しない）
  - ❌ `<ul className="nav-desktop">`（`nav-desktop` という CSS は存在しない）
  - 細かい制御が必要なら `style={{...}}` の inline style か Tailwind arbitrary values（`text-[14px]`, `bg-[#fafafa]`, `gap-[clamp(...)]` 等）を使う
  - Theme.tsx が `.type-h1` `.type-body-md` 等の `.type-<key>` クラスは emit するので、それは使ってよい
- **image_specs は `source: "reuse"` のみ使う。`generate` は禁止**。
  画像は提供された素材 URL からだけ選ぶ。素材に合う画像が無い場面は、
  その画像を使わない設計に変える（タイポグラフィ・色面・余白・SVG 風アイコン等で構成）。
  Codex 画像生成は現在無効化されており、`generate` 指定すると pipeline 全体が失敗する
- 先頭に `<Theme ... />` を 1 回（name / colors / typography / rounded / spacing / motionCharacter / bodyTypography / bodyColor / bgColor を渡す）
- **`colors` / `typography` / `rounded` / `spacing` は必ず JSON 文字列としてシングルクォートで渡す**。
  MDX ランタイムコンパイラはネストされたオブジェクトリテラルを属性値として正しく渡せないため、JSX 式ではなく JSON 文字列にする。
  - ✅ `colors='{{"primary":"#111","neutral":"#faf6ec"}}'`
  - ❌ `colors={{{{primary: "#111", neutral: "#faf6ec"}}}}`（MDX が剥がして空オブジェクトになる）
  - JSON は**厳密な JSON** で書く: キーはダブルクォート、シングルクォートで囲み、属性値の `"` は JSON 内だけで使う
  - 例: `typography='{{"h1":{{"fontFamily":"Zen Kaku Gothic New","fontSize":"clamp(2.2rem,5.5vw,4rem)","fontWeight":800,"lineHeight":1.15}},"h2":{{"fontFamily":"Zen Kaku Gothic New","fontSize":"2rem","fontWeight":700}},"body-md":{{"fontFamily":"Noto Sans JP","fontSize":"1rem","fontWeight":400,"lineHeight":1.95}}}}'`
- **Theme の typography オブジェクトは必ずこの key で渡す**（key 名を変えると要素の自動スタイルが効かなくなる）:
  - 必須: `h1`, `h2`, `h3`, `body-md`, `label-sm`
  - 任意: `h4`, `h5`, `h6`, `body-lg`, `display`, その他の自由な key（`.type-<key>` として class 利用可）
  - 各値は `{{ fontFamily, fontSize, fontWeight, lineHeight, letterSpacing }}`
  - `<h1>` 〜 `<h6>` / `<p>` / `<li>` / `<blockquote>` / `<label>` / `<small>` / `<figcaption>` は
    この typography が自動で当たるので、**MDX 側で font-size / font-weight / font-family を className や style で上書きしない**（Theme に任せる）
- **画像参照は必ずリテラル文字列の属性値として書く**:
  - ✅ `<img src="{{{{img:hero}}}}" />`
  - ✅ `image="{{{{img:hero}}}}"`
  - ❌ JSX のテンプレートリテラル内で動的に組み立てる（例: バッククォートと ${{var}} を使うパターン）。Python の置換器は JSX を評価できないので、画像が 404 になる
  - ❌ `src={{dynamicUrl}}` のように動的変数で URL を解決する書き方も同様
  - 画像 URL を map の中で動的に参照したい場合は、map する元の配列のオブジェクトに `"{{{{img:ROLE}}}}"` を**リテラル文字列のまま**値として持たせ、`<img src={{item.url}}>` で渡す。Python は item.url の値 `{{{{img:ROLE}}}}` を正しく置換できる
- **画像 `ROLE` は必ず IMAGE_SPECS で宣言したものだけ**使う。MDX で新しい role を発明してはいけない。
  MDX 内で使う全ての `{{{{img:ROLE}}}}` の ROLE を IMAGE_SPECS に含めておく（使われない role も含めない）。
  画像を使いたい場所が増えるなら**先に IMAGE_SPECS に足してから** MDX を書く
- CTA の href は `{{{{FORM_URL}}}}` のまま（後で置換される）
- Hero の `title` はプレーン文字列だけ渡す。TextReveal は Hero 内部で自動適用されるので、
  手動で `<TextReveal>` で包むと二重ネストしてクラッシュする
- **`<p>` タグで本文をラップしない**。MDX は `<p>` 内の改行付きテキストを markdown パラグラフと解釈して
  内側をもう 1 回 `<p>` でラップし、HTML の `<p>` ネスト禁止ルールに違反してハイドレーションエラーが出る。
  代わりに:
  - ✅ `<div className="...">本文テキスト</div>` — MDX が `<p>` 相当に正しくレンダリング
  - ✅ 単なる markdown 段落として書く（前後に空行。親が `<section>` や `<div>` ならそのまま `<p>` になる）
  - ❌ `<p className="type-body-lg">\n  本文\n</p>` — MDX が `<p><p>本文</p></p>` に展開してクラッシュ
- JSX 式 attribute（`{{...}}`）は数値・オブジェクト前提の props（`cols={{3}}`, `delay={{0.2}}` 等）にだけ使う。
  リストは children 合成で渡す（例: `<FAQ>` の中に `<FAQItem>` を並べる）
- 属性値の文字列に ASCII の `"` を書かない。強調は「」
- `<script>` 禁止
- ブランドマーク画像が提供されている場合、最初に Read で開いて視認し、パレットと書体、
  Nav / Footer の `logo` prop に反映させる

### 出力形式（この 2 つの delimiter ブロックだけ。前置き・後書き・コードフェンス一切なし）

<!-- IMAGE_SPECS:BEGIN -->
[
  {{"role":"hero","source":"reuse","source_url":"<提供URLのどれか>","prompt":null,"aspect_ratio":"16:9","filename":"hero.jpg","alt":"..."}},
  {{"role":"texture","source":"generate","source_url":null,"prompt":"<English prompt>","aspect_ratio":"1:1","filename":"texture.png","alt":"..."}}
]
<!-- IMAGE_SPECS:END -->

<!-- MDX:BEGIN -->
<Theme name="..." colors={{{{...}}}} typography={{{{...}}}} rounded={{{{...}}}} spacing={{{{...}}}} motion_character="..." />
...本体...
<!-- MDX:END -->
"""


# ========================== Validate ==========================

_SRC_ATTR_RE = re.compile(r'(?:src|image)=["\']([^"\']+)["\']')
_IMG_PLACEHOLDER_RE = re.compile(r"\{\{img:([A-Za-z0-9_-]+)\}\}")
# JSX テンプレートリテラル内に placeholder が入っているパターンを検出
# 例: src={`{{img:${p.img}}}`} — Python 置換器では拾えない
_JSX_TEMPLATE_PLACEHOLDER_RE = re.compile(r"`[^`]*\{\{img:[^`]*\$\{[^`]*`")
_CLASSNAME_RE = re.compile(r'className=["\']([^"\']+)["\']')

# 「明らかにセマンティックな未定義 class」だけ検出する。Tailwind 全網羅の whitelist は非現実的なので、
# arvex で禁じる prefix を blacklist する方針。
# - Tailwind には arc / nav / site / page / hero / card / article 等のプレフィックス utility は存在しない
# - これらは Claude が「セマンティック CSS module を定義してる前提」で誤って書く時のシグナル
_FORBIDDEN_CLASS_PREFIXES = (
    "arc-", "nav-", "site-", "page-", "hero-", "card-", "article-", "topfan-",
    "brand-", "footer-", "header-", "section-", "issue-", "post-", "container-",
    "wrapper-", "layout-",
)


def _is_forbidden_semantic_class(token: str) -> bool:
    if not token:
        return False
    # Tailwind の `bg-card` のような known shorthand（実在）と区別: `card-` は forbidden、`bg-card` は OK
    return token.startswith(_FORBIDDEN_CLASS_PREFIXES)


def validate_mdx(mdx: str, image_urls: set[str]) -> None:
    if "<Theme" not in mdx:
        raise ValueError("MDX must include <Theme ... />")
    if "<script" in mdx.lower():
        raise ValueError("<script> tag is forbidden")
    if _JSX_TEMPLATE_PLACEHOLDER_RE.search(mdx):
        raise ValueError(
            "image placeholder found inside JSX template literal with ${} interpolation — "
            "Python replacer cannot resolve this. Use literal `{{img:ROLE}}` as attribute value instead."
        )
    remaining = _IMG_PLACEHOLDER_RE.findall(mdx)
    if remaining:
        raise ValueError(f"unresolved image placeholders: {remaining}")
    # 未定義のセマンティック class 検出（arc-link / nav-desktop 等を防ぐ）
    bad_classes: set[str] = set()
    for class_str in _CLASSNAME_RE.findall(mdx):
        for tok in class_str.split():
            if _is_forbidden_semantic_class(tok):
                bad_classes.add(tok)
    if bad_classes:
        raise ValueError(
            f"外部 CSS が必要なセマンティック class が検出されました: "
            f"{sorted(bad_classes)[:20]}\n"
            f"arvex は team 専用 CSS ファイルを定義していないので、これらは適用されない。"
            f"Tailwind utility か inline style に書き直してください。"
        )
    for src in _SRC_ATTR_RE.findall(mdx):
        if not src or src.startswith("data:") or not src.startswith("http"):
            continue
        if src not in image_urls:
            raise ValueError(f"image src not in provided URLs: {src}")


# ========================== Image resolution (same as before) ==========================

def _resolve_one(spec: ImageSpec, slug: str, tmp_dir: Path) -> dict:
    if spec.source == "reuse":
        print(f"  [img {spec.role}] reuse → {spec.source_url}", flush=True)
        return {
            "role": spec.role,
            "source": "reuse",
            "filename": spec.filename,
            "url": spec.source_url,
            "prompt": None,
            "aspect_ratio": spec.aspect_ratio,
            "alt": spec.alt,
        }
    if not ENABLE_IMAGE_GEN:
        raise ValueError(
            f"IMAGE_SPECS で role={spec.role!r} が source='generate' を指定しているが、"
            f"画像生成は無効化されている（ARVEX_ENABLE_IMAGE_GEN=0）。"
            f"team の素材 URL からの reuse のみ使うよう MDX を組み直してください。"
        )
    print(f"  [img {spec.role}] generate via Codex", flush=True)
    local = tmp_dir / spec.filename
    codex_image.generate(spec.prompt or "", spec.aspect_ratio, local)
    print(f"  [img {spec.role}] upload to Blob", flush=True)
    url = blob.upload(local, f"p/{slug}/{spec.filename}", force=True)
    print(f"  [img {spec.role}] done → {url}", flush=True)
    return {
        "role": spec.role,
        "source": "generate",
        "filename": spec.filename,
        "url": url,
        "prompt": spec.prompt,
        "aspect_ratio": spec.aspect_ratio,
        "alt": spec.alt,
    }


def generate_images(specs: list[ImageSpec], slug: str, known_source_urls: set[str]) -> list[dict]:
    # reuse URL は必ず採取済み assets に存在するものに制限
    for s in specs:
        if s.source == "reuse":
            if not s.source_url or s.source_url not in known_source_urls:
                raise ValueError(
                    f"reuse spec references unknown URL: {s.source_url!r}\n"
                    f"known source URLs: {sorted(known_source_urls)}"
                )
    reuse_count = sum(1 for s in specs if s.source == "reuse")
    gen_count = len(specs) - reuse_count
    print(f"  ({reuse_count} reuse, {gen_count} generate)", flush=True)
    with tempfile.TemporaryDirectory(prefix=f"arvex-{slug}-") as tmp:
        tmp_dir = Path(tmp)
        workers = max(1, gen_count) if gen_count else 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda s: _resolve_one(s, slug, tmp_dir), specs))


# ========================== User prompt ==========================

def _build_user_prompt(
    org: dict,
    brand_mark_url: str | None = None,
    logo_path: Path | None = None,
    interview_transcript: list[dict] | None = None,
    lp_mockup_path: Path | None = None,
) -> str:
    # 画像リスト
    source_assets = []
    if org.get("source_assets"):
        try:
            source_assets = json.loads(org["source_assets"])
        except Exception:
            pass
    if source_assets:
        assets_block = "\n".join(
            f"- {a['type']}  {a['url']}"
            + (f"\n  caption: {(a.get('caption') or '')[:250]}" if a.get("caption") else "")
            for a in source_assets
        )
    else:
        assets_block = "（画像なし。全て generate で埋めてよい）"

    # 生テキスト素材
    source_text = []
    if org.get("source_text"):
        try:
            source_text = json.loads(org["source_text"])
        except Exception:
            pass
    if source_text:
        blocks = []
        for i, s in enumerate(source_text):
            header = f"--- [{i+1}] {s.get('type','')}  {s.get('url','')} ---"
            body = (s.get("content") or "").strip()
            blocks.append(f"{header}\n{body}")
        text_section = "\n\n".join(blocks)
    else:
        text_section = "（生テキスト素材は未収集）"

    # 公開コンテンツの実URL
    pub = {}
    if org.get("published_content"):
        try:
            pub = json.loads(org["published_content"])
        except Exception:
            pass
    ext_links = pub.get("external_links") or []
    articles = pub.get("articles") or []

    links_blocks = []
    if ext_links:
        lines = [f"- [{l.get('platform','web')}] {l['url']}" for l in ext_links]
        links_blocks.append("外部リンク:\n" + "\n".join(lines))
    if articles:
        lines = []
        for a in articles:
            line = f"- [{a.get('platform','')}] {a.get('title','')}\n    url: {a.get('url','')}"
            if a.get("published_at"):
                line += f"\n    date: {a.get('published_at')}"
            if a.get("description"):
                line += f"\n    desc: {a['description'][:200]}"
            if a.get("body"):
                body = a["body"][:2500].replace("\n", " ")
                line += f"\n    body: {body}"
            lines.append(line)
        links_blocks.append("公開記事:\n" + "\n".join(lines))
    verified_links_section = "\n\n".join(links_blocks) if links_blocks else "（公開コンテンツは見つかっていない）"

    # Instagram 投稿の実 URL も使える
    ig_posts = [s for s in source_text if s.get("type") == "ig_post" and s.get("url")]
    ig_urls_section = "\n".join(f"- {p['url']}" for p in ig_posts) if ig_posts else "（なし）"

    # notable_facts: 素材から regex 抽出した固有情報候補
    notable_facts = {}
    if org.get("notable_facts"):
        try:
            notable_facts = json.loads(org["notable_facts"])
        except Exception:
            pass
    facts_block_parts: list[str] = []
    for label, key in [
        ("人名候補（敬称・役職付きで出現したもの）", "names"),
        ("日付候補（素材中に出現）", "dates"),
        ("イベント・企画名候補", "events"),
        ("団体名候補", "orgs"),
        ("場所候補", "places"),
        ("引用句候補（「」で括られていた語）", "quotes"),
    ]:
        items = notable_facts.get(key) or []
        if items:
            lines = "\n".join(f"  - {x}" for x in items[:30])
            facts_block_parts.append(f"**{label}**:\n{lines}")
    if facts_block_parts:
        notable_facts_section = (
            "regex で素材から抽出した**実在候補**（これらは素材中に実際に出現した文字列）。\n"
            "人名・日付・場所・イベント名などを MDX に書く時は**このリストから選ぶ**。"
            "このリストに無い固有情報は書かない（代わりにその言及を削るか抽象化する）:\n\n"
            + "\n\n".join(facts_block_parts)
        )
    else:
        notable_facts_section = "（固有情報候補は抽出されませんでした）"

    brand_mark_section = "（ブランドマークは採取できていません）"
    if brand_mark_url:
        if logo_path:
            brand_mark_section = (
                f"この団体のプロフィール画像（事実上のロゴ / ブランドマーク）があります。\n"
                f"- ローカルパス: `{logo_path}`  ← Read ツールでこの画像を必ず開いて視認してください\n"
                f"- 公開 URL (Blob): {brand_mark_url}  ← MDX の Nav / Footer の logo にそのまま使える\n\n"
                f"画像を見たうえで、色・形・トーンをパレットと書体に反映する（模倣ではなく調和）。"
            )
        else:
            brand_mark_section = (
                f"プロフィール画像 URL: {brand_mark_url}\n"
                f"（ローカル表示に失敗したため色味は推測で構いません）"
            )

    transcript_block = _format_transcript_for_designer(interview_transcript or [])

    mockup_section = "（LP モックアップは生成されていません）"
    if lp_mockup_path and lp_mockup_path.exists():
        mockup_section = (
            f"この団体のために **LP モックアップ画像** を先に Codex に描かせました。\n"
            f"- ローカルパス: `{lp_mockup_path}`  ← **Read ツールで必ず開いて視認してから MDX を書き始めてください**\n\n"
            f"扱い方:\n"
            f"- **視覚ターゲット**として参照する。全体の構図・階層・色温度・書体の雰囲気・セクションの比率を match させる\n"
            f"- ただし**ピクセル完全再現は目指さない**。Codex が描けない細部（実在写真・実在人物）は Claude が素材 URL に差し替える\n"
            f"- モックアップの**雰囲気**を実装の北極星に、**具体値**は Theme token + 団体素材で埋める\n"
            f"- モックアップで示された Hero のコピー・CTA ラベルはヒアリング結果に照らして整合させる（モックアップの方が正確なら優先）"
        )

    return f"""### 団体プロフィール
名前: {org['name']}
所属: {org.get('university') or '不明'}
分類（仮）: {org.get('category') or '未分類'}
bio 要約: {org.get('bio_summary') or ''}
Instagram: @{org.get('instagram') or ''}

### LP モックアップ画像（設計の視覚ターゲット）
{mockup_section}

### ブランドマーク（ロゴ相当のプロフィール画像）
{brand_mark_section}

### ヒアリング記録（団体本人の声。これを HP 設計の最重要入力として扱う）

{transcript_block}

### 実在候補（素材から抽出した固有情報リスト）
{notable_facts_section}

### 生テキスト素材（彼らの言葉そのもの）
{text_section}

### 採取済み画像（reuse 可。source_url にはこのリストの URL をそのまま使う）
{assets_block}

### 実在する公開コンテンツ URL（MDX 内で Card / Nav / Footer のリンクに使える）
{verified_links_section}

### Instagram 投稿 URL（参照可）
{ig_urls_section}

ヒアリング記録と素材に**根ざして**、この団体の HP が何であるべきかを設計し、そのまま MDX として実装してください。
ヒアリングに無い固有情報 / notable_facts に無い固有情報は**発明しない**（削る or 抽象化）。
ブランドマーク画像があるなら、最初に Read で開いて視認した上で設計を始めてください。
"""


# ========================== Interview loop ==========================

INTERVIEW_MAX_ROUNDS = 10


def _format_notable_facts_for_summary(nf: dict) -> str:
    lines: list[str] = []
    for label, key in [
        ("人名", "names"),
        ("引用", "quotes"),
        ("日付", "dates"),
        ("イベント", "events"),
        ("団体", "orgs"),
        ("場所", "places"),
    ]:
        items = (nf or {}).get(key) or []
        if items:
            joined = " / ".join(items[:15])
            lines.append(f"- {label}: {joined}")
    return "\n".join(lines) if lines else "（抽出された固有情報なし）"


def _build_persona_material(org: dict, notable_facts: dict) -> str:
    """persona sub-agent に渡す素材の全文ダンプ。"""
    parts: list[str] = []
    if org.get("bio_summary"):
        parts.append(f"### bio / プロフィール\n{org['bio_summary']}")
    if org.get("notable_facts"):
        parts.append(f"### 素材から抽出された固有情報\n{_format_notable_facts_for_summary(notable_facts)}")
    try:
        source_text = json.loads(org.get("source_text") or "[]")
    except Exception:
        source_text = []
    if source_text:
        chunks = []
        for i, s in enumerate(source_text):
            head = f"[{i+1}] {s.get('type','')}  {s.get('url','')}"
            body = (s.get("content") or "").strip()
            chunks.append(f"{head}\n{body}")
        parts.append("### 素材テキスト\n\n" + "\n\n".join(chunks))
    try:
        pub = json.loads(org.get("published_content") or "{}")
    except Exception:
        pub = {}
    articles = pub.get("articles") or []
    if articles:
        arc_lines = []
        for a in articles:
            line = f"- {a.get('title','')} ({a.get('published_at','')})"
            if a.get("description"):
                line += f"\n  概要: {a['description'][:200]}"
            if a.get("body"):
                line += f"\n  本文: {a['body'][:1500]}"
            arc_lines.append(line)
        parts.append("### 公開記事\n\n" + "\n".join(arc_lines))
    return "\n\n".join(parts) if parts else "（素材なし）"


def _build_interviewer_user_prompt(
    org: dict, notable_facts: dict, transcript: list[dict]
) -> str:
    summary_parts = [
        f"団体名: {org['name']}",
        f"Instagram: @{org.get('instagram') or ''}",
    ]
    if org.get("bio_summary"):
        summary_parts.append(f"bio: {org['bio_summary'][:800]}")
    summary_parts.append("素材から抽出された固有情報:\n" + _format_notable_facts_for_summary(notable_facts))
    summary = "\n\n".join(summary_parts)

    if not transcript:
        transcript_block = "（まだヒアリング未実施。最初のラウンドです）"
    else:
        rounds = []
        for entry in transcript:
            if entry.get("type") == "done":
                continue
            r = entry.get("round")
            q = entry.get("questions", "").strip()
            a = entry.get("answers", "").strip()
            rounds.append(f"--- Round {r} ---\n[質問]\n{q}\n\n[回答]\n{a}")
        transcript_block = "\n\n".join(rounds) if rounds else "（empty）"

    return f"""### 団体概要（参考）

{summary}

### これまでのヒアリング履歴

{transcript_block}

### 次のアクション

追加で聞くべきことがあれば QUESTIONS ブロックで質問を出してください。
情報が十分なら DONE ブロックで締めてください。
"""


def _run_interview(org: dict) -> list[dict]:
    """main agent ↔ persona sub-agent のヒアリングループ。transcript を返す。"""
    try:
        notable_facts = json.loads(org.get("notable_facts") or "{}")
    except Exception:
        notable_facts = {}

    persona_material = _build_persona_material(org, notable_facts)
    persona_sys = PERSONA_SYSTEM_PROMPT_TEMPLATE.format(
        team_name=org["name"],
        material=persona_material,
    )

    transcript: list[dict] = []
    for round_num in range(1, INTERVIEW_MAX_ROUNDS + 1):
        interviewer_user = _build_interviewer_user_prompt(org, notable_facts, transcript)
        try:
            interviewer_out = claude_cli.call_text(
                system_prompt=INTERVIEWER_SYSTEM_PROMPT,
                user_prompt=interviewer_user,
                model=MODEL,
            )
        except Exception as e:
            print(f"[interview] round {round_num}: interviewer call failed: {e} — stopping", flush=True)
            break
        done_block = claude_cli.extract_block(interviewer_out, "DONE")
        if done_block:
            transcript.append({"round": round_num, "type": "done", "content": done_block})
            print(f"[interview] round {round_num}: DONE", flush=True)
            break
        questions = claude_cli.extract_block(interviewer_out, "QUESTIONS")
        if not questions:
            print(f"[interview] round {round_num}: no valid block, stopping. raw head: {interviewer_out[:200]}", flush=True)
            break

        persona_user = (
            f"arvex からの質問です（Round {round_num}）。各質問に順に番号を付けて答えてください。\n\n"
            f"{questions}"
        )
        try:
            persona_out = claude_cli.call_text(
                system_prompt=persona_sys,
                user_prompt=persona_user,
                model=MODEL,
            )
        except Exception as e:
            print(f"[interview] round {round_num}: persona call failed: {e} — stopping", flush=True)
            break
        answers = claude_cli.extract_block(persona_out, "ANSWERS") or persona_out.strip()
        transcript.append({
            "round": round_num,
            "questions": questions,
            "answers": answers,
        })
        print(f"[interview] round {round_num}: Q/A completed", flush=True)
    return transcript


def _format_transcript_for_designer(transcript: list[dict]) -> str:
    if not transcript:
        return "（ヒアリング未実施）"
    lines = []
    for entry in transcript:
        r = entry.get("round")
        if entry.get("type") == "done":
            lines.append(f"--- Round {r} (DONE) ---\n{entry.get('content','')}")
            continue
        q = entry.get("questions", "").strip()
        a = entry.get("answers", "").strip()
        lines.append(f"--- Round {r} ---\n[質問]\n{q}\n\n[回答]\n{a}")
    return "\n\n".join(lines)


# ========================== Designer selection ==========================

DESIGNER_SELECTION_SYSTEM_PROMPT = """あなたは arvex のデザインディレクターです。
団体の素材を読んで、5 人のデザイナーの中から**この団体に最適な 1 人**を選びます。

各デザイナーは固有の思想 / 書体 / 色の嗜好 / モーション癖を持つ。generic に無難なデザイナーは居ない。

### デザイナー候補

{designer_summaries}

### 判断基準

1. 団体の**性格** — 各デザイナーの「思想」と団体のあり方が合うか
2. 団体の**素材プロフィール** — 写真の量・活動の幅・コンテンツの種類
3. 団体の**読者**がデザイナーの表現で動くか

### 具体的な fit ヒント

- 写真 10 枚以上 + 活動が多種多様 → **zine-kid** または **poster-designer** を強く検討
- 取材記事・連載・対話・ポッドキャストが中心、写真は控えめ → **editorial-purist**
- 数字・データ・正確性・コンサル・分析系 → **swiss-minimalist**
- 社会課題・平和・人権・環境・国際支援系 → **brutalist**
- ビジュアル一発で印象を作る集客系（祭・展示・スポーツ・料理） → **poster-designer**

**editorial-purist は default ではない**。明確な「言葉中心」の根拠が無い限り、他のデザイナーを優先検討する。

### 出力形式（前置き後書きなし）

<!-- CHOICE:BEGIN -->
selected: <デザイナーの name スラグ>
reason: <1-2 文で、なぜこのデザイナーか>
ruled_out: <他のデザイナーを除外した理由を 1 文で（特に editorial-purist を選ばなかった理由 or editorial-purist を選んだ場合は他を選ばなかった理由）>
<!-- CHOICE:END -->
"""


def _build_designer_summaries(designers: list[designer_registry.Designer]) -> str:
    lines = []
    for d in designers:
        lines.append(
            f"## {d.name}\n"
            f"- 通称: {d.display_name}\n"
            f"- 思想: {d.description}\n"
            f"- 愛用書体: {', '.join(d.signature_fonts)}\n"
            f"- 色方針: {d.palette_rules}\n"
            f"- モーション性格: {d.motion_profile}"
        )
    return "\n\n".join(lines)


def _select_designer(
    org: dict, notable_facts: dict, transcript: list[dict]
) -> designer_registry.Designer | None:
    designers = designer_registry.load_designers()
    if not designers:
        print("[design] no designers registered", flush=True)
        return None

    summary_parts = [f"団体名: {org['name']}"]
    if org.get("bio_summary"):
        summary_parts.append(f"bio: {org['bio_summary'][:600]}")
    summary_parts.append("notable facts:\n" + _format_notable_facts_for_summary(notable_facts))
    transcript_condensed = _format_transcript_for_designer(transcript)[:3000]
    summary_parts.append(f"ヒアリング transcript:\n{transcript_condensed}")

    # visual signal: 写真の多さ・活動の多様性を Claude に伝える
    visual_signal_lines = []
    try:
        source_assets = json.loads(org.get("source_assets") or "[]")
    except Exception:
        source_assets = []
    post_thumbs = [a for a in source_assets if a.get("type") == "post_thumb"]
    photo_count = len(post_thumbs)
    visual_signal_lines.append(f"- 採取された活動写真: {photo_count} 枚")

    # 各写真 caption の長さ平均（活動の説明が豊富か）
    captions = [(a.get("caption") or "").strip() for a in post_thumbs]
    captions = [c for c in captions if c]
    if captions:
        avg_caption_len = sum(len(c) for c in captions) // len(captions)
        visual_signal_lines.append(f"- 写真キャプションの平均長: {avg_caption_len} 字")

    # bio の活動列挙数を粗く（読点で split）
    bio = org.get("bio_summary") or ""
    activity_count_in_bio = bio.count("、") + bio.count("\n")
    visual_signal_lines.append(f"- bio の語の区切り数: {activity_count_in_bio}（多いほど多様な活動）")

    visual_signal_block = "\n".join(visual_signal_lines) if visual_signal_lines else "（visual signal 取得不可）"
    summary_parts.append("素材の visual 特性:\n" + visual_signal_block)

    user_prompt = "\n\n".join(summary_parts) + "\n\nこの団体に最適なデザイナーを 1 人選んでください。"

    sys_prompt = DESIGNER_SELECTION_SYSTEM_PROMPT.format(
        designer_summaries=_build_designer_summaries(designers)
    )

    try:
        raw = claude_cli.call_text(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            model=MODEL,
        )
    except Exception as e:
        print(f"[design] designer selection failed: {e} — fallback to first designer", flush=True)
        return designers[0]

    choice = claude_cli.extract_block(raw, "CHOICE")
    if not choice:
        print(f"[design] no CHOICE block — fallback to first designer. raw: {raw[:300]}", flush=True)
        return designers[0]
    m = re.search(r"selected:\s*([A-Za-z0-9_-]+)", choice)
    if not m:
        return designers[0]
    slug = m.group(1).strip()
    for d in designers:
        if d.name == slug:
            reason_m = re.search(r"reason:\s*(.+)", choice, re.DOTALL)
            reason = (reason_m.group(1).strip() if reason_m else "")[:200]
            print(f"[design] selected designer: {d.name} ({d.display_name}) — {reason}", flush=True)
            return d
    print(f"[design] unknown designer slug '{slug}' — fallback to {designers[0].name}", flush=True)
    return designers[0]


def _build_design_system_prompt(
    designer: designer_registry.Designer, components_dir: Path
) -> str:
    arvex_tech = SYSTEM_PROMPT.format(components_dir=str(components_dir))
    skill_prelude = _load_frontend_design_prelude()

    parts: list[str] = []
    if skill_prelude:
        parts.append(f"# Foundation: frontend-design skill\n\n{skill_prelude}")
    parts.append(f"# 機能的団体 HP の前提（不変、最優先）\n\n{arvex_tech}")
    parts.append(
        f"# aesthetic の皮（適用層 — 機能的構造を上書きしない）\n\n"
        f"{designer.persona_markdown}\n\n"
        f"このペルソナは aesthetic 表面のみを担当。HP の機能的骨格（Nav / Hero+CTA / "
        f"Activities / Join / Footer）と arvex 実装規約は上書きしない。"
    )
    return "\n\n---\n\n".join(parts)


# ========================== Reader review + revise loop ==========================

READER_REVIEW_SYSTEM_PROMPT_TEMPLATE = """あなたは学生団体「{team_name}」の中の人（または意思決定者）で、自分たちの**公式 HP**としてこのページを使う前提で評価します。
Instagram の DM で「HP のラフを作ったから見て」とリンクが送られてきて、スマホで開いたところです。
デザインの専門知識はありません。**団体の活動現場を知っている目線**で、30 秒で判断します。

**重要**: このページは団体の**永続的な公式 HP として使う**ものであって、一回きりの editorial や proposal 資料ではない。
評価の軸は「**自団体の常用 HP としてこれを使えるか**」。

スクショ (desktop + mobile) を Read で必ず両方開いて、下記のチェックリストに答えてください。

### チェックリスト（12 項目、機能的な団体 HP として成立するか）

1. 3 秒で「何の団体か」がわかる？
2. **自分たちの団体として認識できる**？（自分たちの写真・活動名・言葉が使われていて、違和感なく「我々の HP」と思えるか）
3. **HP 内に arvex 等の外部制作者の自己言及がない**？（"from arvex" "arvex 編集部が..." "Proposal for" "叩き台" "bulletin" "号数" 等のメタ情報が無い）
4. **刊行物っぽい時間マーカーがない**？（"Vol.01" "春号" "spring issue" "MMXXVI" のような**一回性**を示す表記が無い）
5. やっている**活動が具体的に見える**？（抽象的な自己紹介だけでなく、実活動の列挙 / 写真 / 外部リンクがある）
6. **外部リンクが機能的**？（note 記事、IG 投稿、フォームへのリンクが実在 URL として使われている）
7. **連絡 / 参加方法が 3 秒以内に見つかる**？（申し込みフォーム / DM / オープンチャット等）
8. モバイルで読みやすい？（文字サイズ、行間、overflow、折り返し）
9. 壊れてない？（画像欠け、レイアウト崩れ、プレースホルダ残留）
10. 実活動写真が使われている？（Codex 生成の抽象画像に逃げていない）
11. 嘘や捏造がない？（やっていないこと、言っていない言葉、存在しない人名がない）
12. **永続的に使える**と思える？（「季節の刊行物」的に賞味期限が短くない、常用 HP として維持できる）

### 出力形式（前置き後書きなし）

<!-- REVIEW:BEGIN -->
## 評価
1. [pass/fail] 短いコメント
2. [pass/fail] 短いコメント
3. [pass/fail] 短いコメント
4. [pass/fail] 短いコメント
5. [pass/fail] 短いコメント
6. [pass/fail] 短いコメント
7. [pass/fail] 短いコメント
8. [pass/fail] 短いコメント
9. [pass/fail] 短いコメント
10. [pass/fail] 短いコメント
11. [pass/fail] 短いコメント
12. [pass/fail] 短いコメント

## 総合判定
VERDICT: PASS or NEEDS_REVISION
(9 個以上 pass、**かつ 3 番と 4 番は必ず pass** なら PASS。それ以外は NEEDS_REVISION)

## デザイナーへの具体的フィードバック（NEEDS_REVISION の場合のみ。何をどう直すかを具体的に）
- ...
<!-- REVIEW:END -->
"""


REVISION_WITH_FEEDBACK_USER_TEMPLATE = """### あなたが前回作った MDX

```mdx
{mdx_prev}
```

### 読者からのフィードバック

```
{review}
```

### レンダリング結果のスクショ（Read で確認）
{shots_block}

読者のフィードバックに従って MDX を修正してください。

制約:
- あなたのペルソナは**維持**する（中間的な無難さに寄らない）
- 指摘された問題だけを直し、問題ない箇所は触らない
- 画像 URL はそのまま維持
- `{{FORM_URL}}` プレースホルダはそのまま
- MDX 技術制約 (p ネスト禁止、Theme JSON、JSX 属性制限 等) は維持

出力は MDX ブロックだけ:

<!-- MDX:BEGIN -->
...修正後 MDX 全文...
<!-- MDX:END -->
"""


MAX_REVIEW_ITERATIONS = 3


def _screenshot_proposal(slug: str, out_dir: Path) -> list[Path]:
    """dev server の /p/<slug> を desktop + mobile でスクショして保存。"""
    from playwright.sync_api import sync_playwright

    paths: list[Path] = []
    url = f"{DEV_SERVER_URL}/p/{slug}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vw_name, vw, vh in [("desktop", 1440, 900), ("mobile", 390, 844)]:
            ctx = browser.new_context(viewport={"width": vw, "height": vh})
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)
            path = out_dir / f"{vw_name}.png"
            page.screenshot(path=str(path), full_page=True)
            paths.append(path)
            ctx.close()
        browser.close()
    return paths


def _run_reader_review(
    *,
    slug: str,
    org: dict,
    shots_dir: Path,
) -> tuple[str, bool]:
    """IG DM 読者視点でレビュー。戻り値: (review_text, is_pass)。"""
    shot_paths = sorted(shots_dir.glob("*.png"))
    shots_block = "\n".join(f"- `{p}`" for p in shot_paths)
    sys_prompt = READER_REVIEW_SYSTEM_PROMPT_TEMPLATE.format(team_name=org["name"])
    user_prompt = (
        f"スクショ:\n{shots_block}\n\n"
        f"両方とも Read で開いてから、チェックリストで判定してください。"
    )
    try:
        raw = claude_cli.call_text(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            model=MODEL,
            tools="Read",
            allowed_dirs=[str(shots_dir)],
        )
    except Exception as e:
        print(f"[reader-review] call failed: {e}", flush=True)
        return "", True  # fail-open: pass to avoid infinite retry
    review = claude_cli.extract_block(raw, "REVIEW") or raw.strip()
    is_pass = bool(re.search(r"VERDICT:\s*PASS\b", review))
    return review, is_pass


def _revise_with_designer(
    *,
    designer: designer_registry.Designer,
    mdx_prev: str,
    review: str,
    components_dir: Path,
    shots_dir: Path,
    image_urls: set[str],
    form_url: str | None,
) -> str | None:
    """designer にレビュー feedback を渡して MDX を改訂。成功時改訂 MDX、失敗時 None。"""
    sys_prompt = _build_design_system_prompt(designer, components_dir)
    shots_block = "\n".join(f"- `{p}`" for p in sorted(shots_dir.glob("*.png")))
    mdx_for_review = mdx_prev
    if form_url and form_url in mdx_for_review:
        mdx_for_review = mdx_for_review.replace(form_url, "{{FORM_URL}}")
    user_prompt = REVISION_WITH_FEEDBACK_USER_TEMPLATE.format(
        mdx_prev=mdx_for_review,
        review=review,
        shots_block=shots_block,
    )
    allowed: list[str] = [str(components_dir), str(shots_dir)]
    if designer.moodboard_dir.exists():
        allowed.append(str(designer.moodboard_dir))
    try:
        raw = claude_cli.call_text(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            model=MODEL,
            tools="Read",
            allowed_dirs=allowed,
        )
    except Exception as e:
        print(f"[revise] call failed: {e}", flush=True)
        return None
    revised = claude_cli.extract_block(raw, "MDX")
    if not revised:
        return None
    check_mdx = revised.replace("{{FORM_URL}}", form_url) if form_url else revised
    try:
        validate_mdx(check_mdx, image_urls)
    except ValueError as e:
        print(f"[revise] revised MDX invalid: {e}", flush=True)
        return None
    return revised


def _review_and_revise_loop(
    *,
    designer: designer_registry.Designer,
    slug: str,
    org: dict,
    mdx_current: str,
    components_dir: Path,
    image_urls: set[str],
    form_url: str | None,
) -> tuple[str, list[dict]]:
    """読者レビュー → 修正を最大 MAX_REVIEW_ITERATIONS 回ループ。
    戻り値: (最終 MDX, review の履歴)。PASS したら即 return。"""
    history: list[dict] = []
    if not REVIEW_ENABLED:
        return mdx_current, history
    try:
        httpx.get(f"{DEV_SERVER_URL}/p/{slug}", timeout=5)
    except Exception as e:
        print(f"[review] dev server unreachable: {e} — skipping loop", flush=True)
        return mdx_current, history

    for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
        with tempfile.TemporaryDirectory(prefix=f"arvex-shots-{slug}-{iteration}-") as tmp_shots:
            shots_dir = Path(tmp_shots)
            try:
                print(f"[review] iteration {iteration}: taking screenshots", flush=True)
                _screenshot_proposal(slug, shots_dir)
            except Exception as e:
                print(f"[review] screenshot failed: {e} — ending loop", flush=True)
                break

            print(f"[review] iteration {iteration}: running reader review", flush=True)
            review, is_pass = _run_reader_review(slug=slug, org=org, shots_dir=shots_dir)
            history.append({
                "iteration": iteration,
                "review": review,
                "verdict": "PASS" if is_pass else "NEEDS_REVISION",
            })
            if is_pass:
                print(f"[review] iteration {iteration}: PASS — ending loop", flush=True)
                break
            if iteration >= MAX_REVIEW_ITERATIONS:
                print(f"[review] iteration {iteration}: still NEEDS_REVISION at max — accepting current", flush=True)
                break

            print(f"[review] iteration {iteration}: NEEDS_REVISION — revising with designer {designer.name}", flush=True)
            revised = _revise_with_designer(
                designer=designer,
                mdx_prev=mdx_current,
                review=review,
                components_dir=components_dir,
                shots_dir=shots_dir,
                image_urls=image_urls,
                form_url=form_url,
            )
            if revised is None:
                print(f"[review] revise failed — keeping current MDX and ending loop", flush=True)
                break
            # form_url 置換
            final = revised.replace("{{FORM_URL}}", form_url) if form_url else revised
            # DB に反映して次 iteration で dev server が新しい MDX を読む
            db.execute(
                "UPDATE proposals SET mdx = ? WHERE slug = ?",
                [final, slug],
            )
            mdx_current = final
            print(f"[review] iteration {iteration}: revised MDX saved, continuing loop", flush=True)

    return mdx_current, history


# ========================== Main orchestration ==========================

def slugify(handle: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", handle or "org").strip("-").lower()
    return s or "org"


def generate_and_save(org_id: str, form_url: str | None = None) -> str:
    org = db.get_org(org_id)
    if not org:
        raise ValueError(f"Org not found: {org_id}")

    slug = slugify(org.get("instagram") or org_id[:8])
    components_dir = (Path(__file__).resolve().parent.parent / "web" / "components" / "proposal").resolve()

    source_assets_list = []
    if org.get("source_assets"):
        try:
            source_assets_list = json.loads(org["source_assets"])
        except Exception:
            pass
    brand_mark_url = next(
        (a["url"] for a in source_assets_list if a.get("type") == "profile_pic"),
        None,
    )

    # ヒアリング: main agent ↔ team persona sub-agent の Q&A ループ。
    print(f"[interview] starting main ↔ persona loop (max {INTERVIEW_MAX_ROUNDS} rounds) ...", flush=True)
    interview_transcript = _run_interview(org)
    print(f"[interview] completed: {len(interview_transcript)} round(s)", flush=True)

    # デザイナー選択: 5 人のペルソナから team に最適な 1 人
    try:
        notable_facts_dict = json.loads(org.get("notable_facts") or "{}")
    except Exception:
        notable_facts_dict = {}
    designer = _select_designer(org, notable_facts_dict, interview_transcript)
    if not designer:
        raise RuntimeError("no designer could be selected")

    with tempfile.TemporaryDirectory(prefix=f"arvex-logo-{slug}-") as tmp_logo_dir, \
         tempfile.TemporaryDirectory(prefix=f"arvex-mockup-{slug}-") as tmp_mockup_dir:
        tmp_logo_path = Path(tmp_logo_dir)
        tmp_mockup_path_dir = Path(tmp_mockup_dir)
        logo_path: Path | None = None
        if brand_mark_url:
            logo_path = _download_logo(brand_mark_url, tmp_logo_path)
            if logo_path:
                print(f"  brand mark downloaded: {logo_path}", flush=True)

        # LP モックアップ生成: Codex で AI 画像生成。`ENABLE_IMAGE_GEN` が True の時のみ実行。
        # 既定は False (Codex usage limit / コスト懸念) で、素材写真だけで HP を構成する。
        mockup_image_path: Path | None = None
        mockup_url: str | None = None
        if ENABLE_IMAGE_GEN:
            print(f"[mockup] asking Codex for LP design reference ...", flush=True)
            mockup_image_path = lp_mockup.prepare_mockup(
                designer=designer,
                org=org,
                transcript=interview_transcript,
                slug=slug,
                tmp_dir=tmp_mockup_path_dir,
            )
            if mockup_image_path is None:
                print(f"[mockup] failed or skipped — continuing without visual target", flush=True)
            else:
                try:
                    mockup_url = blob.upload(
                        mockup_image_path,
                        f"p/{slug}/mockup.png",
                        force=True,
                    )
                    print(f"[mockup] uploaded to Blob → {mockup_url}", flush=True)
                except Exception as e:
                    print(f"[mockup] Blob upload failed: {e} — continuing with local path only", flush=True)
        else:
            print(f"[mockup] image generation disabled (set ARVEX_ENABLE_IMAGE_GEN=1 to enable)", flush=True)

        user_prompt = _build_user_prompt(
            org,
            brand_mark_url=brand_mark_url,
            logo_path=logo_path,
            interview_transcript=interview_transcript,
            lp_mockup_path=mockup_image_path,
        )
        system_prompt = _build_design_system_prompt(designer, components_dir)

        # Read 許可 dir: components + logo tmp + designer の moodboard + mockup
        allowed: list[str] = [str(components_dir)]
        if logo_path:
            allowed.append(str(tmp_logo_path))
        if mockup_image_path:
            allowed.append(str(tmp_mockup_path_dir))
        if designer.moodboard_dir.exists():
            allowed.append(str(designer.moodboard_dir))
            print(f"[generate] moodboard available: {len(designer.moodboard_paths())} images at {designer.moodboard_dir}", flush=True)

        print(f"[generate] designer={designer.name} — inference ...", flush=True)
        raw = claude_cli.call_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=MODEL,
            tools="Read",
            allowed_dirs=allowed,
        )

    specs_text = claude_cli.extract_block(raw, "IMAGE_SPECS")
    mdx_text = claude_cli.extract_block(raw, "MDX")
    if not specs_text:
        raise ValueError(f"missing IMAGE_SPECS block:\n{raw[:2000]}")
    if not mdx_text:
        raise ValueError(f"missing MDX block:\n{raw[:2000]}")

    raw_specs = json.loads(specs_text)
    specs = [ImageSpec.model_validate(s) for s in raw_specs]
    print(f"  {len(specs)} image specs planned", flush=True)

    known_source_urls = {a["url"] for a in source_assets_list}
    print(f"[images] resolving", flush=True)
    images = generate_images(specs, slug, known_source_urls)

    role_to_url = {img["role"]: img["url"] for img in images}
    mdx = _IMG_PLACEHOLDER_RE.sub(
        lambda m: role_to_url.get(m.group(1)) or m.group(0),
        mdx_text,
    )

    image_urls = {img["url"] for img in images}
    validate_mdx(mdx, image_urls)

    if form_url:
        mdx = mdx.replace("{{FORM_URL}}", form_url)

    expires_at = (datetime.now() + timedelta(days=PROPOSAL_TTL_DAYS)).isoformat()
    proposal_id = db.insert_proposal(org_id=org_id, slug=slug, expires_at=expires_at)
    db.update_proposal(
        proposal_id,
        form_url=form_url,
        vercel_url=f"/p/{slug}",
        design_brief=raw,
        interview=json.dumps(interview_transcript, ensure_ascii=False),
        mockup_url=mockup_url,
        images=json.dumps(images, ensure_ascii=False),
        mdx=mdx,
    )
    db.update_org(org_id, status="proposal_sent")
    print(f"\nProposal v1 saved: {proposal_id} (designer={designer.name})", flush=True)
    print(f"  preview: /p/{slug}", flush=True)

    # Reader review + revise loop: IG DM 読者視点の審査 → 修正を最大 MAX_REVIEW_ITERATIONS 回
    final_mdx, review_history = _review_and_revise_loop(
        designer=designer,
        slug=slug,
        org=org,
        mdx_current=mdx,
        components_dir=components_dir,
        image_urls=image_urls,
        form_url=form_url,
    )

    # 最終結果と history を DB に保存
    if review_history:
        brief_with_review = (
            raw
            + f"\n\n---\n\n[DESIGNER={designer.name}]\n\n[REVIEW_HISTORY]\n\n"
            + json.dumps(review_history, ensure_ascii=False, indent=2)
        )
    else:
        brief_with_review = raw + f"\n\n[DESIGNER={designer.name}]"
    db.update_proposal(
        proposal_id,
        design_brief=brief_with_review,
        mdx=final_mdx,
    )
    if review_history:
        verdicts = [h["verdict"] for h in review_history]
        print(f"[review] completed {len(review_history)} iteration(s). verdicts: {verdicts}", flush=True)
    return proposal_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.hp_generator <org_id> [form_url]")
        sys.exit(1)
    org_id = sys.argv[1]
    form_url = sys.argv[2] if len(sys.argv) > 2 else None
    generate_and_save(org_id, form_url)


if __name__ == "__main__":
    main()
