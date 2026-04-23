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
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, field_validator

from scripts import blob, claude_cli, codex_image, db


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

SYSTEM_PROMPT = """あなたは学生団体のための home page を設計・実装するデザイナー兼エンジニアです。

素材を読んで、この団体の HP が何であるべきかを自分で言葉にし、その設計をそのまま MDX として実装します。
出力は 1 回で、IMAGE_SPECS（画像仕様 JSON）と MDX 本体の 2 つの delimiter ブロック。

### 実装の自由度

MDX は React + Tailwind がそのまま動く環境です。組み方は 3 段階あり、**既存部品に合わせる必要はない**:

1. **素の HTML + Tailwind**: `<div className="...">` `<section>` `<a>` `<img>` `<ul>` `<h2>` 等を直接書ける。
   Tailwind のユーティリティクラスも任意で使える（`flex`, `grid`, `gap-8`, `text-4xl`, `rounded-full` 等）。
   既存の Hero / Section / Card 等が合わないレイアウトは、素 HTML で組む方が自然。
2. **既存のラッパ部品**: `{components_dir}` に `Hero.tsx`, `Card.tsx`, `Grid.tsx` 等のラッパがある。
   この団体のデザインに**合えば**使う。合わなければ無視してよい。Read で props と挙動を確認できる。
3. **自作モーション**: `{components_dir}/motion/primitives.tsx` に `MotionDiv`, `MotionSection`,
   `MotionSpan`, `MotionA`, `MotionH1` 等の motion-enabled 要素がある。これらに `initial` / `animate` /
   `whileInView` / `transition` 等を自分で書いて、この団体専用のモーションを自作できる。
   例: `<MotionSection initial={{{{ opacity: 0 }}}} whileInView={{{{ opacity: 1 }}}} transition={{{{ duration: 1.2 }}}}>...</MotionSection>`
   既成の `<Reveal>` `<TextReveal>` `<Stagger>` 等も使えるが、それは参考であって正解ではない。

どの段階をどう混ぜるかは、この団体のデザインにとって何が必要かで決める。

### 守るルール

- **素材にない固有情報（人名・日付・場所・実績数字）は書かない**。代わりに:
  - その言及ごと削る
  - より抽象度の高い書き方に置き換える（例: 「[取材 01]さんとの対話回」ではなく「NPO 代表との対話回」or その記述自体を削除）
  - プレースホルダとして目立って残すくらいなら、削る / 抽象化する方が良い
- 性格付けや役割を書く時は、団体自身が使っている語を使う
- image_specs は reuse を優先。提供された URL から選ぶ。不足分のみ generate
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


# ========================== User prompt ==========================

def _build_user_prompt(org: dict, brand_mark_url: str | None = None, logo_path: Path | None = None) -> str:
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

    return f"""### 団体プロフィール
名前: {org['name']}
所属: {org.get('university') or '不明'}
分類（仮）: {org.get('category') or '未分類'}
bio 要約: {org.get('bio_summary') or ''}
Instagram: @{org.get('instagram') or ''}

### ブランドマーク（ロゴ相当のプロフィール画像）
{brand_mark_section}

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

この団体の HP が何であるべきかを自分で言葉にして、そのまま MDX として実装してください。
ブランドマーク画像があるなら、最初に Read で開いて視認した上で設計を始めてください。
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

    with tempfile.TemporaryDirectory(prefix=f"arvex-logo-{slug}-") as tmp_logo_dir:
        tmp_logo_path = Path(tmp_logo_dir)
        logo_path: Path | None = None
        if brand_mark_url:
            logo_path = _download_logo(brand_mark_url, tmp_logo_path)
            if logo_path:
                print(f"  brand mark downloaded: {logo_path}", flush=True)

        user_prompt = _build_user_prompt(org, brand_mark_url=brand_mark_url, logo_path=logo_path)
        system_prompt = SYSTEM_PROMPT.format(components_dir=str(components_dir))

        allowed: list[str] = [str(components_dir)]
        if logo_path:
            allowed.append(str(tmp_logo_path))

        print(f"[generate] single-turn inference ...", flush=True)
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
