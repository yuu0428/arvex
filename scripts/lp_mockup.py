"""LP (landing page) mockup generator.

選定された Designer と団体のヒアリング結果 (transcript) から、
その団体専用の LP モックアップ画像 (モバイル縦長 9:16) を Codex で 1 枚生成する。
デザイナー選択後、本番 MDX を書く前の「ビジュアル下書き」として使う想定。

Usage:
    from scripts import designer_registry, lp_mockup
    designer = designer_registry.get_designer("azusa")
    mockup_path = lp_mockup.prepare_mockup(designer, org, transcript, slug, tmp_dir)

副作用: `tmp_dir` に PNG を書き出すのみ（DB / Blob / ネットワーク I/O は持たない）。
Codex の失敗時は None を返しログに出力する（例外は投げない）。
"""
import json
import re
import subprocess  # noqa: F401 — reserved for future direct codex calls
from pathlib import Path

from scripts import codex_image, designer_registry


# ========================== Prompt template ==========================

# Codex の AI image generation を明示的に呼ぶための prompt。
# 「rendered design illustration」「AI-generated」「photographic mockup」等の signal で
# Codex が Python UI コードを書こうとせず、画像生成 API に直行するようにする。
CODEX_MOCKUP_TEMPLATE_SHORT = """\
Use AI image generation (OpenAI image API) to produce a single rendered design
mockup illustration. This is a photographic, designer-style PNG output —
not a Python-drawn diagram, not a PIL/Pillow rendering, not an HTML
screenshot. Generate the image with the image generation tool.

Subject: a vertical 9:16 mobile landing page design mockup for a real Japanese
student organization. Treat it as a high-fidelity Behance/Dribbble case-study
preview rendered as one continuous tall artboard.

Team displayed on the page: {team_name}
Hero text (render this exact Japanese in the page, do not translate):
  "{hero_copy}"
Primary CTA button label (exact Japanese):
  "{main_cta}"
3-4 small activity tiles, each labelled with this Japanese (verbatim):
{activities_block}

Visual direction (designer = {designer_name}):
- Aesthetic note: {designer_oneliner}
- Palette: {palette_rules}
- Typography family to depict: {signature_fonts_list}

Composition top to bottom on the same 9:16 artboard:
1. thin top bar with the team wordmark
2. hero block with the Japanese hero text + a clear CTA button labelled with the Japanese above
3. row(s) of 3-4 small activity tiles — show the Japanese tile labels, no fake stock-photo faces
4. CTA band restating the button
5. quiet footer line

Critical rules:
- All Japanese text must be readable and rendered correctly (no garbled glyphs, no Chinese hanzi substitution).
- No phone bezel, no browser chrome, no laptop frame — it is the LP itself.
- No purple-gradient generic SaaS aesthetic; obey the palette above.
- No fake testimonials, no English placeholder text, no lorem ipsum.

Save the rendered PNG (the AI-generated image) to: {output_path}
"""


CODEX_MOCKUP_TEMPLATE = """\
You are a senior art director producing a high-fidelity mobile landing-page
mockup for a real Japanese student organization. Target fidelity: top-ranked
Behance / Dribbble post. This image will be used by a frontend engineer as a
visual reference to implement the actual web page, so clarity beats novelty.

====================================================================
CONTEXT — the team this page is for
====================================================================
Team name          : {team_name}
One-line tagline   : {team_tagline}
Audience           : {audience}
Unique strength    : {unique_strength}
Hero copy (exact)  : {hero_copy}
Primary CTA label  : {main_cta}

Activities (render as tiles, 3-4 of these):
{activities_block}

====================================================================
ART DIRECTION — follow this designer persona strictly
====================================================================
Designer: {designer_display_name} ({designer_name})

{designer_persona_body}

Signature fonts (use these, nothing else):
{signature_fonts_list}

Palette rules:
{palette_rules}

Motion / energy profile (reflect in layout rhythm):
{motion_profile}

{designer_specific_overrides}

Ignore any default SaaS aesthetic you may have seen in training data. Follow
the persona above instead.

====================================================================
MOODBOARD REFERENCES
====================================================================
Before you draw, OPEN and STUDY these reference images. Match their
typographic rhythm, color temperature, paper/texture feel, and composition
logic. Do NOT copy any single reference literally — synthesize the language.

{moodboard_block}

====================================================================
LAYOUT — mobile 9:16, vertical scroll, ONE continuous artboard
====================================================================
Compose a single tall frame (9:16) that reads like a real LP screenshot
stitched from top to bottom. Include these sections in this order:

1. Top bar (~7% height)
   - Small wordmark on the left (team name in the signature display font)
   - A single minimal nav hint on the right (e.g. "Menu" or a thin icon)
   - Respect the designer's palette for background and stroke

2. Hero (~38% height)
   - Render the hero copy VERBATIM: "{hero_copy}"
     (Do not paraphrase, do not translate, do not shorten.)
   - Secondary line from the tagline: "{team_tagline}"
   - A primary CTA button labeled exactly: "{main_cta}"
   - Supporting visual: abstract shape / texture / distant silhouette ONLY.
     NO detailed human faces, NO realistic stock photography of people,
     NO AI-looking generic portraits.

3. Activities (~32% height)
   - 3-4 tiles, each showing the activity name + one-line description.
     Copy provided above — render verbatim, Japanese intact.
   - Tile styling follows the designer's card / grid philosophy.
   - Differentiate tiles by texture, color block, or type hierarchy —
     NOT by fake photos of people.

4. CTA band (~15% height)
   - Restate "{main_cta}" as a large button or wordmark
   - One supporting sentence drawn from the unique strength:
     "{unique_strength}"

5. Footer (~8% height)
   - Small wordmark, a thin rule, a placeholder for contact line
   - Respect the designer's type scale — keep it quiet

====================================================================
HARD CONSTRAINTS — do NOT violate these
====================================================================
- The artboard is 9:16 portrait. Treat it as a single screenshot, not a
  collage of unrelated screens.
- All Japanese text must be rendered CORRECTLY (no glitched kanji, no
  Chinese hanzi substitution). If a Japanese glyph cannot be drawn
  faithfully, switch to a cleaner alternative font rather than producing
  garbled characters.
- Use ONLY the signature fonts listed above. No Inter unless the persona
  lists Inter. No generic SaaS typography.
- Palette must obey the designer's palette_rules above. No purple gradient
  hero. No default Tailwind indigo-500.
- NO lorem ipsum. NO placeholder English. All copy is the Japanese strings
  given above, rendered verbatim.
- NO detailed people. Faces, hands, and stock-photo portraits are banned.
  Silhouettes, backs of heads, crowd textures from distance are OK.
- NO AI-slop UI chrome: no floating 3D orbs, no glassmorphism blobs, no
  generic "hero mockup inside a laptop frame", no fake iPhone bezels.
- NO badges / ratings / "as seen on" logos / fake testimonials.
- This is the LP itself, not a device mockup. No phone bezels, no browser
  chrome, no laptop frames.
- No placeholder text. Every string is the provided Japanese. Any empty
  slot is a design error.
- Contrast must remain legible.

====================================================================
FIDELITY TARGET
====================================================================
Think: a real screenshot of a production LP, captured on a mobile device,
as it would appear in a portfolio case-study carousel on Dribbble. Every
section must feel designed by a human who read the brief, not assembled
from a template.

====================================================================
OUTPUT
====================================================================
Generate exactly ONE image at 9:16 aspect ratio. Save as PNG to:
{output_path}

Do not ask questions. Do not generate variants. Do not write any files
other than the PNG above. Quit after saving.
"""


# Designer-specific overrides (persona を画像モックアップ向けに補強する追加指示)
_DESIGNER_OVERRIDES: dict[str, str] = {
    "editorial-purist": """\
EXTRA GUIDANCE FOR editorial-purist:
- Paper-like cream background (#F4EFE6 — #EDE6D6 range). Body copy in a
  very dark brown-black, never pure #000.
- Type hierarchy is built from mincho sizes alone; no bold sans for
  emphasis. Accent color is used at 10% of surface maximum, as a thin
  rule or a single stamped word.
- Generous vertical whitespace between sections. Think printed magazine
  margin, not SaaS dashboard.
- No drop shadows, no rounded-2xl cards with soft glow. If a card is
  needed, it is a hairline rule on cream, nothing more.""",
    "zine-kid": """\
EXTRA GUIDANCE FOR zine-kid:
- Background: cream / off-white with a subtle paper grain texture.
- Headings in Yusei Magic (or handwritten-feeling alternative), tilted
  by -2 to +3 degrees. Tape corners (masking-tape strips) allowed on 2-3
  elements, not everywhere.
- Use 3-5 bright accents: fluorescent yellow, coral, sky, mint. Dot
  patterns, scribbled underlines, small stamp motifs OK.
- It is hand-made but NOT childish — this is a design student's zine,
  not a kindergarten poster. Information still has to be readable.""",
    "swiss-minimalist": """\
EXTRA GUIDANCE FOR swiss-minimalist:
- Strict 12-column alignment. Every text block and tile sits on a
  shared baseline grid. Hairline (1px) rules divide sections.
- Only ONE accent color (red, blue, or yellow — pick based on the team's
  unique_strength tone). Everything else is black, white, off-white,
  and at most two steps of gray.
- Small uppercase kicker labels (e.g. "01 — ACTIVITIES") with tight
  letter-spacing (~0.2em). Numerals in a mono face.
- No decorative illustration, no texture, no gradient. Whitespace is the
  decoration.""",
    "brutalist": """\
EXTRA GUIDANCE FOR brutalist:
- Black background OR stark white — pick one and commit. Accent is
  blood red (#FF0033) OR fluorescent yellow (#FFFF00), not both.
- Headings in Bebas Neue (condensed ultra-bold), body in Courier /
  JetBrains Mono. Mixed case is fine but emphasis uses ALL CAPS.
- Box outlines (2-4px hard borders), intentional asymmetry, small
  overlaps between sections. Timestamp markers in corners
  (e.g. "v1 — 2026.04") are encouraged, but NOT as magazine issue
  numbers — they are build-tags.
- No smooth gradients, no soft shadows, no rounded corners larger
  than 2px.""",
    "poster-designer": """\
EXTRA GUIDANCE FOR poster-designer:
- Hero occupies closer to 45% of the artboard and reads like a printed
  poster — one strong image / texture layer, type set on top of it in
  ultra-condensed display (Anton / Archivo Black / Abril Fatface).
- Palette is derived FROM the hero layer (analogous / duotone), not
  picked abstractly. Accent colors: 2 max.
- Subsequent sections (activities, CTA, footer) DROP the poster intensity
  and become a calm, readable grid — only the hero is cinematic. The
  rest reads like a normal LP body.
- Parallax feel can be implied by layered type overlapping the image
  edge by a few percent.""",
}


def _build_moodboard_block(paths: list[Path]) -> str:
    if not paths:
        return "  (no moodboard provided — rely on persona description only)"
    # Codex は画像を多く開かせると処理が重くなるので 3 枚まで
    return "\n".join(f"  - Open: {p.resolve()}" for p in paths[:3])


def _build_fonts_list(fonts: list[str]) -> str:
    if not fonts:
        return "  - (use persona default)"
    return "\n".join(f"  - {f}" for f in fonts)


# ========================== Prompt building ==========================

def build_codex_prompt(
    designer: designer_registry.Designer,
    team_ctx: dict,
    moodboard_paths: list[Path] | None = None,
) -> str:
    """Codex に渡す LP モックアップ画像生成プロンプトを構築する。

    Codex の image-gen mode は長文プロンプトで stalling/timeout する傾向があるため、
    既定では SHORT テンプレートを使う。必須要素（team / hero / activities / aesthetic）
    だけ凝縮し、moodboard の Read 指示等は含めない。
    moodboard_paths は将来用に signature 残してあるが現在は未使用。
    """
    activities = team_ctx.get("activities", []) or []
    activities_lines: list[str] = []
    for i, a in enumerate(activities[:4], start=1):
        name = (a.get("name") or "").strip()
        desc = (a.get("description") or "").strip()
        if name and desc:
            activities_lines.append(f"  {i}. {name} — {desc}")
        elif name:
            activities_lines.append(f"  {i}. {name}")
        elif desc:
            activities_lines.append(f"  {i}. {desc}")
    activities_block = "\n".join(activities_lines) if activities_lines else "  (no activities provided)"

    # designer 一行要約: SKILL.md 全文ではなく description だけ渡す
    designer_oneliner = (designer.description or "").strip().split("\n", 1)[0][:200]

    return CODEX_MOCKUP_TEMPLATE_SHORT.format(
        team_name=team_ctx.get("team_name", ""),
        hero_copy=team_ctx.get("hero_copy", ""),
        main_cta=team_ctx.get("main_cta", "仲間になる"),
        activities_block=activities_block,
        designer_name=designer.name,
        designer_oneliner=designer_oneliner,
        signature_fonts_list=", ".join(designer.signature_fonts or []) or "(persona default)",
        palette_rules=designer.palette_rules or "",
        output_path="{output_path}",  # runtime substitution
    )


# ========================== Image generation ==========================

def generate_mockup_image(
    prompt: str,
    output_path: Path,
    timeout: int = 900,
) -> Path:
    """Codex に 9:16 の LP モックアップ画像を 1 枚生成させる。

    `build_codex_prompt` 側で末尾に `Save to {output_path} ...` 指示が含まれているため、
    ここで `{output_path}` プレースホルダを実パスに差し替えたうえで `codex_image.generate`
    を呼ぶ。

    Args:
        prompt: `build_codex_prompt` の戻り値。`{output_path}` を含んでいる想定
        output_path: 書き出し先 PNG の絶対パス
        timeout: 秒（既定 600）

    Returns:
        実際に保存された Path（`codex_image.generate` が失敗した場合は例外が伝播）
    """
    resolved_prompt = prompt.replace("{output_path}", str(output_path))
    return codex_image.generate(
        prompt=resolved_prompt,
        aspect_ratio="9:16",
        output_path=output_path,
        timeout=timeout,
    )


# ========================== Transcript parsing helpers ==========================

_QUESTIONS_BLOCK_RE = re.compile(r"<!--\s*QUESTIONS:BEGIN\s*-->(.*?)<!--\s*QUESTIONS:END\s*-->", re.DOTALL)
_ANSWERS_BLOCK_RE = re.compile(r"<!--\s*ANSWERS:BEGIN\s*-->(.*?)<!--\s*ANSWERS:END\s*-->", re.DOTALL)
_NUMBERED_ITEM_RE = re.compile(r"^\s*\d+\.\s*(.+?)\s*$", re.MULTILINE)
_QUOTE_RE = re.compile(r"「([^」]{3,80})」")


def _extract_numbered_items(text: str) -> list[str]:
    """`1. ...` 形式の行を素朴に拾う。"""
    if not text:
        return []
    items = _NUMBERED_ITEM_RE.findall(text)
    return [i.strip() for i in items if i.strip()]


def _first_answer_from_transcript(transcript: list[dict]) -> str:
    """最初の Round の最初の回答（Q1 の A1）を拾う。無ければ空文字。"""
    for entry in transcript or []:
        if entry.get("type") == "done":
            continue
        ans = entry.get("answers", "") or ""
        inner = _ANSWERS_BLOCK_RE.search(ans)
        body = inner.group(1) if inner else ans
        items = _extract_numbered_items(body)
        if items:
            return items[0]
    return ""


def _done_content(transcript: list[dict]) -> str:
    for entry in transcript or []:
        if entry.get("type") == "done":
            return entry.get("content", "") or ""
    return ""


def _extract_done_field(done: str, label_regex: str) -> str:
    """DONE ブロック内の `- {label}: ...` を拾う。複数行対応。"""
    if not done:
        return ""
    # `- 把握できたこと: ...` 形式。次の `- ` または末尾までを拾う
    pat = rf"-\s*{label_regex}\s*:\s*(.+?)(?=\n\s*-\s|\Z)"
    m = re.search(pat, done, re.DOTALL)
    return m.group(1).strip() if m else ""


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    # 日本語の句点 / 改行で切る
    parts = re.split(r"[。\n]", text, maxsplit=1)
    return parts[0].strip() if parts else text.strip()


def _extract_hero_copy(transcript: list[dict]) -> str:
    """transcript 全体から「」引用 or 短くて強い一文を拾う。"""
    corpus_parts: list[str] = []
    for entry in transcript or []:
        if entry.get("type") == "done":
            corpus_parts.append(entry.get("content", "") or "")
        else:
            corpus_parts.append(entry.get("answers", "") or "")
    corpus = "\n".join(corpus_parts)
    quotes = _QUOTE_RE.findall(corpus)
    if quotes:
        # 最初の「」引用を返す
        return quotes[0].strip()
    # fallback: 最初の回答の先頭 1 文
    first = _first_answer_from_transcript(transcript)
    return _first_sentence(first)[:80]


def _activities_from_org(org: dict) -> list[dict]:
    """org.source_assets の IG post caption から活動項目を 3-5 件作る。"""
    try:
        assets = json.loads(org.get("source_assets") or "[]")
    except Exception:
        assets = []
    activities: list[dict] = []
    for a in assets:
        caption = (a.get("caption") or "").strip()
        if not caption:
            continue
        # タイトル候補: 最初の行 or 最初の 24 文字
        first_line = caption.split("\n", 1)[0].strip()
        name = first_line[:40]
        desc_full = caption.replace("\n", " ").strip()
        activities.append({
            "name": name,
            "description": desc_full[:80],
        })
        if len(activities) >= 5:
            break
    return activities[:5]


def _avoid_images_from_designer(designer: designer_registry.Designer) -> str:
    """SKILL.md persona から「避けたい」系の記述を雑に抽出。無ければ空文字。"""
    md = designer.persona_markdown or ""
    hits: list[str] = []
    for line in md.splitlines():
        if re.search(r"(避け|嫌い|禁止|NG|やらない|しない)", line):
            stripped = line.strip().lstrip("-*#> ").strip()
            if stripped:
                hits.append(stripped)
        if len(hits) >= 3:
            break
    return " / ".join(hits)


# ========================== Public orchestration ==========================

def prepare_mockup(
    designer: designer_registry.Designer,
    org: dict,
    transcript: list[dict],
    slug: str,
    tmp_dir: Path,
) -> Path | None:
    """団体・transcript から LP モックアップ画像を 1 枚作って tmp_dir に保存する。

    Args:
        designer: 選定済みデザイナー
        org: `scripts.db.get_org` の戻り値想定の dict
        transcript: `hp_generator._run_interview` の戻り値想定の list
        slug: ファイル名に使うスラグ
        tmp_dir: 出力先（Path, 事前に存在していなくても mkdir される）

    Returns:
        成功時: 生成された PNG の Path
        失敗時: None（ログに原因を出す）
    """
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # team_name
    team_name = org.get("name", "") or ""

    # team_tagline: 最初の回答 or bio 先頭 1 文。長文回答は切り詰めてプロンプト膨張を防ぐ
    tagline_raw = _first_answer_from_transcript(transcript)
    if not tagline_raw:
        tagline_raw = org.get("bio_summary") or ""
    tagline = _first_sentence(tagline_raw)[:140]

    # DONE ブロックから audience / 強み を拾う
    done = _done_content(transcript)
    grasped = _extract_done_field(done, r"把握できたこと")
    direction = _extract_done_field(done, r"HP の方向性の核")

    # audience: 「把握できたこと」からキーワード「届けたい」「ターゲット」「相手」
    audience = ""
    if grasped:
        m = re.search(r"(届けたい|ターゲット|相手|対象)[^。\n]*", grasped)
        audience = m.group(0).strip() if m else _first_sentence(grasped)

    # unique_strength: 方向性の核 or 強み系キーワード
    unique_strength = ""
    if direction:
        unique_strength = _first_sentence(direction)
    if not unique_strength and grasped:
        m = re.search(r"(強み|独自|らしさ|特徴)[^。\n]*", grasped)
        unique_strength = m.group(0).strip() if m else ""

    # hero_copy: 「」引用 or 最初の答えから
    hero_copy = _extract_hero_copy(transcript) or _first_sentence(tagline)

    team_ctx = {
        "team_name": team_name,
        "team_tagline": tagline,
        "audience": audience,
        "unique_strength": unique_strength,
        "hero_copy": hero_copy,
        "activities": _activities_from_org(org),
        "main_cta": "仲間になる",
        "avoid_images": _avoid_images_from_designer(designer),
    }

    # 注意: moodboard パスを Codex に渡すと、`Open: <path>` 指示をファイル Read と解釈して
    # timeout するので、ここでは空リストを渡す（persona 記述で aesthetic を伝えるだけで十分）
    prompt = build_codex_prompt(designer, team_ctx, moodboard_paths=[])

    output_path = tmp_dir / f"{slug}-lp-mockup.png"
    print(f"[lp_mockup] generating mockup for slug={slug} designer={designer.name} → {output_path}", flush=True)
    try:
        result_path = generate_mockup_image(prompt, output_path)
    except subprocess.TimeoutExpired as e:
        print(f"[lp_mockup] codex timeout: {e}", flush=True)
        return None
    except Exception as e:
        print(f"[lp_mockup] codex failed: {type(e).__name__}: {e}", flush=True)
        return None

    print(f"[lp_mockup] saved: {result_path}", flush=True)
    return result_path


# ========================== Self-test ==========================

if __name__ == "__main__":
    # モックでプロンプト組み立てだけ確認する
    class _MockDesigner:
        name = "mock"
        display_name = "Mock Designer"
        description = "quiet editorial voice"
        signature_fonts = ["Zen Kaku Gothic New", "Inter"]
        palette_rules = "muted neutrals, single accent"
        motion_profile = "slow fades, minimal"
        persona_markdown = "- 派手なグラデーションは避ける\n- 絵文字は使わない"
        dir = Path("/tmp/mock")
        moodboard_dir = Path("/tmp/mock/moodboard")
        favorites_path = Path("/tmp/mock/favorites.json")

    mock_team_ctx = {
        "team_name": "テスト団体",
        "team_tagline": "学生 10 人で地域を巡るフィールドワークサークル。",
        "audience": "同世代の、まだ一歩踏み出せていない学生",
        "unique_strength": "毎週の現地訪問と事後の書き起こし",
        "hero_copy": "完璧じゃなくていい",
        "activities": [
            {"name": "週次フィールドワーク", "description": "毎週土曜に現地を歩く"},
            {"name": "記録会", "description": "火曜に気づきを書き起こす"},
        ],
        "main_cta": "仲間になる",
        "avoid_images": "派手なグラデーション / AI っぽい抽象テクスチャ",
    }

    prompt = build_codex_prompt(_MockDesigner(), mock_team_ctx)
    print("=" * 60)
    print("build_codex_prompt output:")
    print("=" * 60)
    print(prompt)
    print("=" * 60)
    print(f"prompt length: {len(prompt)} chars")
    assert "{output_path}" in prompt, "prompt must leave {output_path} placeholder"
    assert "Generate exactly ONE image" in prompt
    print("OK: structural assertions passed")
