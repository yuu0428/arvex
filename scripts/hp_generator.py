"""2ターン1セッションで提案HPを生成する。

    Turn 1 (session start):
        入力 = 生の素材（bio + 投稿原文 + 関連記事 + 採取画像リスト）
        出力 = DESIGN.md + IMAGE_SPECS（delimited ブロック）
        Claude はここで団体の性格・audience・方針を"頭の中で"構築する

    [image generation]
        Codex で並列生成 + Vercel Blob にアップロード

    Turn 2 (--resume same session):
        入力 = 生成画像の URL 群
        出力 = MDX（delimited ブロック）
        Claude は Turn 1 の思考をそのまま持っているので DESIGN.md を"翻訳"ではなく"続き"として書ける

Usage:
    python -m scripts.hp_generator <org_id> [form_url]
"""
import json
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from scripts import blob, claude_cli, codex_image, db

MODEL = "opus"
PROPOSAL_TTL_DAYS = 10


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


# ========================== Prompts ==========================

TURN1_SYSTEM_PROMPT = """あなたは学生団体のための home page を設計・実装するデザイナー兼エンジニアです。

下記は**1つの思考の流れ**として通しでやります:
1. Turn 1（今ここ）: 生素材を読む → 団体の audience と伝えたいことを心で決める → DESIGN.md を書く → 必要画像の spec を列挙する
2. [この間に画像を生成する機械的ステップが入る]
3. Turn 2（次のターン、同セッション）: 生成画像 URL を受け取って MDX を書く

**Turn 1 で構築した思考は Turn 2 でもそのまま引き継がれます**。
だから Turn 1 の出力は "形式的な仕様書" ではなく、"次の自分のための本気の設計" として書くこと。

### 守るルール
- 既存のデザインジャンル名（editorial / magazine / bento / zine / dossier / brutalist 等）に自分の設計を当てはめない
- 入力素材にない固有情報（人名・日付・具体的取材対象名・実績数字）を発明しない
- image_specs で source:"reuse" を優先、提供された画像 URL の中から選ぶ。不足分のみ source:"generate"
- 団体の audience（協賛候補 / 取材先 / 行政 / 同世代学生 / 新規参加者など）は活動データから自分で推定する

### 出力形式

必ず下記の順で**2つの delimiter ブロック**を出力。前置き・後書き・コードフェンス一切なし:

<!-- DESIGN.md:BEGIN -->
---
name: <団体名>
colors:
  primary: "#hex"
  secondary: "#hex"
  tertiary: "#hex"
  neutral: "#hex"
typography:
  h1:
    fontFamily: <Google Fonts 実在名>
    fontSize: <Xpx>
    fontWeight: <number>
    lineHeight: <number or Xpx>
    letterSpacing: <Xem>
  h2: {...}
  h3: {...}
  body-md: {...}
  label-sm: {...}
rounded:
  sm: 4px
  md: 8px
  lg: 16px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 32px
  xl: 64px
motion_character: <その団体のための motion の性格を自分の言葉で 1〜2 文。既存のラベル（subtle / playful 等）に寄せない。例: 「紙に文字が置かれるように、静かに・ゆっくり到達する」「取材ノートをめくるような抑えたリズム」「新歓期の熱量を反映して跳ねる」>
---

## Overview
<団体の性格・届けたい相手・起こしたい反応を 2〜3 段落で>

## Colors
<各色の役割と、なぜこの色を選んだかの理由>

## Typography
<書体の選定理由と使い分け>

## Layout
<構造・余白の方針>

## Shapes
<角丸・エッジの方針>

## Do's and Don'ts
- Do ...
- Don't ...
<!-- DESIGN.md:END -->

<!-- IMAGE_SPECS:BEGIN -->
[
  {"role":"hero","source":"reuse","source_url":"<提供URLのどれか>","prompt":null,"aspect_ratio":"16:9","filename":"hero.jpg","alt":"..."},
  {"role":"texture","source":"generate","source_url":null,"prompt":"<English prompt>","aspect_ratio":"1:1","filename":"texture.png","alt":"..."}
]
<!-- IMAGE_SPECS:END -->

### YAML の注意
YAML frontmatter 内の文字列値では ASCII の " を使ってよい（YAML の正規文法）。
markdown prose の中では、強調したい日本語を 「」 で囲む（" は避ける）。
"""


TURN2_USER_PROMPT_TEMPLATE = """画像が揃いました。Turn 2 として MDX を出力してください。

### 使える画像（role → url）
{images_block}

### 本物のリンクがあれば使ってよい

Turn 1 のユーザープロンプトに「実在する公開コンテンツ URL」と「Instagram 投稿 URL」のリストがあった。
Card / Nav / Footer で**特定のコンテンツを指す場面**があれば、実在 URL を `href` として使える（任意）。
- note 記事を Card で引用するなら href にその記事 URL
- 外部リンクとして note / 公式サイト / 主要 SNS を Footer/Nav に置いてもよい
- Instagram 投稿 URL は**あれば選択肢として使える**くらい。必須ではない
- 該当 URL が無い場面は href を付けない（空リンクや # は書かない）

### 使える MDX 部品

- <Theme name colors typography rounded spacing bodyTypography bodyColor bgColor />
  ※ Theme は DESIGN.md のトークンを**そのまま object literal として**渡す唯一の特別部品。
  例:
    <Theme
      name="Xxx"
      colors={{{{primary: "#1A1C1E", secondary: "#6C7278", tertiary: "#B8422E", neutral: "#F7F5F2"}}}}
      typography={{{{
        h1: {{{{fontFamily: "Public Sans", fontSize: "48px", fontWeight: 600, lineHeight: 1.1, letterSpacing: "-0.02em"}}}},
        "body-md": {{{{fontFamily: "Public Sans", fontSize: "16px", fontWeight: 400, lineHeight: 1.6}}}}
      }}}}
      rounded={{{{sm: "4px", md: "8px"}}}}
      spacing={{{{xs: "4px", sm: "8px", md: "16px", lg: "32px", xl: "64px"}}}}
    />
- <Nav brand="...">  <NavItem label="..." href="..." />  ... </Nav>
- <Hero eyebrow title subtitle image imageAlt ctaLabel ctaHref variant="centered"|"split"|"minimal" />
- <Section eyebrow title intro tone="default"|"muted"|"inverted">...</Section>
- <Grid cols={{3}} gap="md">...</Grid>
- <Card title description image imageAlt href eyebrow />
- <Stats>  <Stat value="..." label="..." description="..." />  ... </Stats>
- <FAQ>  <FAQItem q="..." a="..." />  ... </FAQ>
- <CTA title description label href />
- <AudienceCTA audience description label href />
- <Quote author source>引用テキスト</Quote>
- <Image src alt caption aspect="16/9"|"4/3"|"3/2"|"1/1"|"9/16" rounded />
- <Prose>...地の文...</Prose>
- <Footer brand="...">  <FooterLine>text</FooterLine>  <FooterLink href="..." label="..." />  ... </Footer>

### モーション部品

**モーションは任意のデコレーションではなく、この HP の設計宣言の一部**です。
DESIGN.md の `motion_character` に書いた性格に**忠実に**、部品の選択と強度を決めてください。

利用可能な部品:

- <Reveal variant="fade"|"up"|"down"|"left"|"right"|"scale" delay={{0}} duration={{0.7}} distance={{32}}>...</Reveal>
    viewport 入りで1度だけ表出。Section や大きなブロックの wrapper に。
- <Stagger delay={{0.08}}>...</Stagger>
    子要素を一つずつ遅延表出。Grid 内の Card の並びなどに。
- <Parallax speed={{0.3}}>...</Parallax>
    スクロール進捗に bind した微小 translate。背景・画像レイヤーに。
- <Magnetic strength={{18}}>...</Magnetic>
    マウスに引き寄せられる挙動。CTA ボタンや重要リンクに。
- <Tilt max={{8}}>...</Tilt>
    3D tilt。Card の奥行き演出に。
- <Ticker from={{0}} to={{150}} duration={{1.4}} prefix="" suffix="人" />
    数字のカウントアップ。素材中に実在する数字のみ。
- <TextReveal by="word"|"char" stagger={{0.05}}>見出しテキスト</TextReveal>
    見出しを単語/文字単位で下から表出。Hero の h1 や主要 h2 に。
- <Marquee direction="left"|"right" speed="slow"|"medium"|"fast">...</Marquee>
    無限スクロール帯。英字ラベル、section divider に。

### motion の敷き方（ゆるい指針）

- **完全静止の HP は arvex として成立しません**。訪問者が最初の数秒で「動きのあるサイト」と感じるレベルの motion を入れる。
- **Hero に初見の motion を必ず入れる**。訪問者が一番最初に目にする部分なので、ここが静止だと全体が静止に見える。最低限どれかを採用:
  - Hero の h1（title）を <TextReveal> で包む
  - または Hero 全体を <Reveal variant="up" duration={{1.2}}> で包む
  - さらに Hero 画像があれば <Parallax speed={{0.2}}> で薄く奥行きを付けてもよい
- どの motion をどこでどの強度で使うかは **motion_character に沿って決定する**（機械的なテンプレ埋めは禁止）:
  - 静謐寄りの character: Reveal / Stagger を控えめに。TextReveal や Marquee は使わない
  - 落ち着き寄りの character: Hero に TextReveal か強めの Reveal、主要 Section に Reveal、Card 列に Stagger、CTA に Magnetic
  - 躍動寄りの character: 上記全部 + 数字に Ticker、Card に Tilt、英字ラベルに Marquee、h2 にも TextReveal
- **見出しを活用する motion は特に効く**: Hero の h1 が TextReveal で出てくると印象が強い。躍動系なら h2 にも使ってよい
- 使用目安: 合計 **5〜12 箇所**（静謐 5 前後、躍動 10 前後）
- Motion 部品は**必ず既存のコンテンツ部品（Hero/Section/Card 等）をラップする形**で使う。空の Motion は禁止
- `prefers-reduced-motion: reduce` の端末は自動で静止表示になる（心配しなくてよい）

### 守るルール

- **先頭に必ず <Theme ... />** を1回だけ置く（DESIGN.md frontmatter のトークンをそのまま）
- 画像 URL は上記リストのものをそのまま参照
- CTA リンクの href は `{{{{FORM_URL}}}}` のままにする（後で置換される）
- **固有情報を発明しない**。入力素材にない人名・日付・具体的取材対象名・実績数字を勝手に書かない
- 該当箇所は下記のプレースホルダを使う:
    `[<役割名の普通名詞> <連番>]`   例: `[取材 01]` `[協力者 01]` `[開催日 01]` `[メンバー 01]`
    もっともらしい架空のタイトル・説明文・固有名詞で埋めない
- 単独 slot（リストでない）は `[役割名]` のみでよい  例: `[代表者名]` `[お問い合わせメール]`
- h1/h2/h3 のタイトルは**業務的・簡潔な語彙**。団体名に引っかけた詩的比喩、文芸的なサブタイトル、体言止めの決め台詞は禁止
    × 弧を描いて、山梨と重なる / 弧は、重なって円になる
    ○ 取材記事 / 最近の放送 / 協賛をご検討の方へ
- JSX 式 attribute（`{{[...]}}` のような配列 props）は <Theme> / <Grid cols={{3}}> / <Ticker from={{0}} to={{N}}> / <Reveal delay={{0.2}}> 等の**数値・オブジェクト前提の props** 以外では使わない
  →  複数要素は必ず children 合成（<FAQ> の中に <FAQItem> を並べる方式）で渡す
- 属性値の文字列内で ASCII の " は使わない。強調は 「」 を使う
- <script> 禁止

### 出力

必ずこの1つの delimiter ブロックだけを出力:

<!-- MDX:BEGIN -->
(ここに MDX 本体。最初に <Theme .../>、次に <Nav>、<Hero>、複数の <Section>、<Footer>。)
<!-- MDX:END -->
"""


# ========================== Parse / Validate ==========================

def parse_design_md(design_md: str) -> dict:
    """DESIGN.md の YAML frontmatter を返す。"""
    m = re.match(r"^---\n(.*?)\n---", design_md.strip(), re.DOTALL)
    if not m:
        raise ValueError("DESIGN.md missing YAML frontmatter")
    try:
        tokens = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse failed: {e}\n\n{m.group(1)[:2000]}")
    if not tokens.get("colors"):
        raise ValueError("DESIGN.md missing colors")
    if not tokens.get("typography"):
        raise ValueError("DESIGN.md missing typography")
    return tokens


_SRC_ATTR_RE = re.compile(r'(?:src|image)=["\']([^"\']+)["\']')


def validate_mdx(mdx: str, image_urls: set[str]) -> None:
    if "<Theme" not in mdx:
        raise ValueError("MDX must include <Theme ... />")
    if "<script" in mdx.lower():
        raise ValueError("<script> tag is forbidden")
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


# ========================== Turn 1 user prompt ==========================

def _build_turn1_user_prompt(org: dict) -> str:
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
        lines = [
            f"- [{a.get('platform','')}] {a.get('title','')}\n    url: {a.get('url','')}"
            + (f"\n    date: {a.get('published_at','')}" if a.get("published_at") else "")
            + (f"\n    desc: {a['description'][:200]}" if a.get("description") else "")
            for a in articles
        ]
        links_blocks.append("公開記事:\n" + "\n".join(lines))
    verified_links_section = "\n\n".join(links_blocks) if links_blocks else "（公開コンテンツは見つかっていない）"

    # Instagram 投稿の実 URL も使える
    ig_posts = [s for s in source_text if s.get("type") == "ig_post" and s.get("url")]
    ig_urls_section = "\n".join(f"- {p['url']}" for p in ig_posts) if ig_posts else "（なし）"

    return f"""### 団体プロフィール
名前: {org['name']}
所属: {org.get('university') or '不明'}
分類（仮）: {org.get('category') or '未分類'}
bio 要約: {org.get('bio_summary') or ''}
Instagram: @{org.get('instagram') or ''}

### 生テキスト素材（彼らの言葉そのもの。ここから activity / voice / audience を読み取る）
{text_section}

### 採取済み画像（reuse 可。source_url にはこのリストの URL をそのまま使う）
{assets_block}

### 実在する公開コンテンツ URL（MDX 生成時に Card の href や Nav/Footer のリンクに使える）
{verified_links_section}

### Instagram 投稿 URL（参照可）
{ig_urls_section}

Turn 1 として DESIGN.md と IMAGE_SPECS を出力してください。
"""


# ========================== Main orchestration ==========================

def slugify(handle: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", handle or "org").strip("-").lower()
    return s or "org"


def generate_and_save(org_id: str, form_url: str | None = None) -> str:
    org = db.get_org(org_id)
    if not org:
        raise ValueError(f"Org not found: {org_id}")

    slug = slugify(org.get("instagram") or org_id[:8])

    # --- Turn 1: DESIGN.md + IMAGE_SPECS ---
    session_id = claude_cli.new_session_id()
    print(f"[turn 1] session={session_id}  DESIGN.md + IMAGE_SPECS", flush=True)
    turn1_user = _build_turn1_user_prompt(org)
    out1 = claude_cli.session_turn(
        session_id=session_id,
        user_prompt=turn1_user,
        system_prompt=TURN1_SYSTEM_PROMPT,
        resume=False,
        model=MODEL,
    )

    design_md = claude_cli.extract_block(out1, "DESIGN.md")
    specs_text = claude_cli.extract_block(out1, "IMAGE_SPECS")
    if not design_md:
        raise ValueError(f"Turn 1 missing DESIGN.md block:\n{out1[:2000]}")
    if not specs_text:
        raise ValueError(f"Turn 1 missing IMAGE_SPECS block:\n{out1[:2000]}")

    design_tokens = parse_design_md(design_md)
    print(f"  colors: {list((design_tokens.get('colors') or {}).keys())}", flush=True)
    print(f"  typography: {list((design_tokens.get('typography') or {}).keys())}", flush=True)

    raw_specs = json.loads(specs_text)
    specs = [ImageSpec.model_validate(s) for s in raw_specs]
    print(f"  {len(specs)} image specs planned", flush=True)

    # --- Image generation ---
    source_assets = []
    if org.get("source_assets"):
        try:
            source_assets = json.loads(org["source_assets"])
        except Exception:
            pass
    known_source_urls = {a["url"] for a in source_assets}
    print(f"[stage 2] resolving images", flush=True)
    images = generate_images(specs, slug, known_source_urls)

    # --- Turn 2 (resume): MDX ---
    images_block = "\n".join(
        f"- {img['role']}: {img['url']}  (aspect {img['aspect_ratio']}, alt: {img['alt']})"
        for img in images
    )
    turn2_user = TURN2_USER_PROMPT_TEMPLATE.format(images_block=images_block)
    print(f"[turn 2] (resume session={session_id})  MDX", flush=True)
    out2 = claude_cli.session_turn(
        session_id=session_id,
        user_prompt=turn2_user,
        resume=True,
        model=MODEL,
    )
    mdx = claude_cli.extract_block(out2, "MDX")
    if not mdx:
        raise ValueError(f"Turn 2 missing MDX block:\n{out2[:2000]}")
    image_urls = {img["url"] for img in images}
    validate_mdx(mdx, image_urls)
    if form_url:
        mdx = mdx.replace("{{FORM_URL}}", form_url)

    # --- Save ---
    expires_at = (datetime.now() + timedelta(days=PROPOSAL_TTL_DAYS)).isoformat()
    proposal_id = db.insert_proposal(org_id=org_id, slug=slug, expires_at=expires_at)
    db.update_proposal(
        proposal_id,
        form_url=form_url,
        vercel_url=f"/p/{slug}",
        design_brief=design_md,  # DESIGN.md 全文
        images=json.dumps(images, ensure_ascii=False),
        mdx=mdx,
    )
    db.update_org(org_id, status="proposal_sent")
    print(f"\nProposal saved: {proposal_id}")
    print(f"  preview: /p/{slug}")
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
