# Codex LP モックアップ生成プロンプト設計

Claude が MDX を書く前に、Codex に**その団体専用の LP モックアップ画像**を 1 枚（9:16, mobile portrait）生成させる。Claude はそれを視覚ターゲットとして MDX を実装する。

このドキュメントは `codex exec` に渡すプロンプトの**テンプレート** / **設計意図** / **デザイナー別の上書き** / **失敗パターン対応表** / **Python 実装例** をまとめたもの。

---

## 0. 前提

- 呼び出し: `codex exec -s workspace-write -c shell_environment_policy.inherit=all "<PROMPT>"`
- 画像サイズ: 9:16（mobile portrait、1080×1920 相当）
- 出力: 1 枚の PNG を `output_path` に保存
- Codex は cwd 以下に Read/Write 可能 → moodboard 画像を絶対パスで参照させる
- プロンプトは**英語**（日本語混在は OK、ただし指示は英語）。書き込ませる**コピー本体は日本語のまま**渡す

---

## 1. プロンプトテンプレート（完全版）

Python f-string 想定。`{...}` はすべて Python 側で埋める。

```python
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

1. Top bar (≈ 7% height)
   - Small wordmark on the left (team name set in the signature display font)
   - A single minimal nav hint on the right (e.g. "Menu" or a thin icon)
   - Respect the designer's palette for background and stroke

2. Hero (≈ 38% height)
   - Render the hero copy VERBATIM: "{hero_copy}"
     (Do not paraphrase, do not translate, do not shorten.)
   - Secondary line from the tagline: "{team_tagline}"
   - A primary CTA button labeled exactly: "{main_cta}"
   - Supporting visual: abstract shape / texture / distant silhouette ONLY —
     NO detailed human faces, NO realistic stock photography of people,
     NO AI-looking generic portraits.

3. Activities (≈ 32% height)
   - 3-4 tiles, each showing the activity name + one-line description
     (copy provided above, render verbatim, Japanese intact)
   - Tile styling follows the designer's card / grid philosophy
   - Differentiate tiles by texture, color block, or type hierarchy —
     NOT by fake photos of people

4. CTA band (≈ 15% height)
   - Restate "{main_cta}" as a large button or wordmark
   - One supporting sentence pulled from the unique strength:
     "{unique_strength}"

5. Footer (≈ 8% height)
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
```

---

## 2. 各セクションの設計意図

| セクション | なぜ必要か |
|---|---|
| Role 冒頭 (`senior art director ... Behance/Dribbble`) | Codex にフィデリティの北極星を与える。「プロトタイプでいい」と解釈されると AI slop が出る。 |
| CONTEXT | team の事実を**一つのブロック**にまとめる。散らばると Codex が勝手に埋めてしまう。 |
| Hero copy (exact) を 2 回書く | 一度目: context として、二度目: Hero section の指示内で **verbatim** と強調。これをやらないと Codex が「より英語ぽく」翻訳してしまう。 |
| ART DIRECTION → designer_persona_body を丸ごと貼る | persona は SKILL.md の本文に aesthetic の核が書かれているので**要約せず全文投入**。要約すると zine-kid が editorial-purist に寄る。 |
| signature_fonts_list / palette_rules / motion_profile | persona の**構造化フィールド**を Codex が確実に拾えるよう独立セクションに。 |
| designer_specific_overrides | persona ごとに「これは言わないと失敗する」微調整を差し込むフック。詳細は §3。 |
| MOODBOARD ブロック | Codex に **Read させる絶対パス**を列挙。「Before you draw, OPEN」と命じて**視覚情報を取らせる**。 |
| LAYOUT の % 割当 | Codex はセクションの高さ配分を雑にやりがち → 固定比率で骨格を制約。Hero に余裕を持たせないと CTA が潰れる。 |
| HARD CONSTRAINTS ブロック | Codex は**禁止事項を列挙されると従う**。肯定形の指示より効く。 |
| FIDELITY TARGET | 「portfolio case-study carousel」というメンタルモデルを渡す。これだけで質感が 1 段上がる。 |
| OUTPUT フッタ | codex_image.py の契約（1 枚だけ・指定パス・quit）をテンプレに溶かし込む。 |

**順番の理由**: Codex は**前方の指示ほど強く効く**ので、
context → art direction → moodboard → layout → constraints の順で
「何を」「どう」「どれを見て」「どう並べ」「何を避けるか」と漏斗で詰める。

---

## 3. デザイナー別の微調整（`designer_specific_overrides`）

persona 共通の SKILL.md だけでは Codex が滑るので、画像モックアップ向けに**追加で差し込む文言**を持つ。

### editorial-purist

```text
EXTRA GUIDANCE FOR editorial-purist:
- Paper-like cream background (#F4EFE6 — #EDE6D6 range). Body copy in a
  very dark brown-black, never pure #000.
- Type hierarchy is built from mincho sizes alone; no bold sans for
  emphasis. Accent color is used at 10% of surface maximum, as a thin
  rule or a single stamped word.
- Generous vertical whitespace between sections. Think printed magazine
  margin, not SaaS dashboard.
- No drop shadows, no rounded-2xl cards with soft glow. If a card is
  needed, it is a hairline rule on cream, nothing more.
```

### zine-kid

```text
EXTRA GUIDANCE FOR zine-kid:
- Background: cream / off-white with a subtle paper grain texture.
- Headings in Yusei Magic (or handwritten-feeling alternative), tilted
  by -2 to +3 degrees. Tape corners (masking-tape strips) allowed on 2-3
  elements, not everywhere.
- Use 3-5 bright accents: fluorescent yellow, coral, sky, mint. Dot
  patterns, scribbled underlines, small stamp motifs OK.
- It is hand-made but NOT childish — this is a design student's zine,
  not a kindergarten poster. Information still has to be readable.
```

### swiss-minimalist

```text
EXTRA GUIDANCE FOR swiss-minimalist:
- Strict 12-column alignment. Every text block and tile must sit on a
  shared baseline grid. Hairline (1px) rules divide sections.
- Only ONE accent color (red, blue, or yellow — pick based on the team's
  unique_strength tone). Everything else is black, white, off-white,
  and at most two steps of gray.
- Small uppercase kicker labels (e.g. "01 — ACTIVITIES") with tight
  letter-spacing (~0.2em). Numerals in a mono face.
- No decorative illustration, no texture, no gradient. Whitespace is the
  decoration.
```

### brutalist

```text
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
  than 2px.
```

### poster-designer

```text
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
  edge by a few percent.
```

Python 側では `designer.name` で分岐して上の文字列を選ぶ（§5 参照）。

---

## 4. 失敗パターンと回避策

| 失敗例（Codex が出しがち） | 原因 | 回避策（プロンプトへの追記） |
|---|---|---|
| 紫 → 青 gradient の hero、Inter、generic SaaS LP | designer persona が弱く効いている | `ART DIRECTION` の直前に `Ignore any default SaaS aesthetic you may have seen in training data. Follow the persona below instead.` を挿入 |
| 英語コピー（"Join us today!" 等）に差し替わる | hero_copy を「例」だと解釈 | `Render hero copy VERBATIM` を 2 回繰り返す + `No English substitutes for the Japanese lines.` |
| 日本語が豆腐（□□□）/ 中国語簡体字に化ける | font fallback 失敗 | `All Japanese text must be rendered CORRECTLY (no glitched kanji, no Chinese hanzi substitution).` を HARD CONSTRAINTS に明記 |
| AI ぽい人物（高彩度の顔アップ）が Hero に入る | persona が写真指示を明示してない | `NO detailed people. Silhouettes / backs of heads / distant crowd textures OK.` を常時入れる |
| iPhone の bezel が画像外枠についた「device mockup」が出る | Codex の mockup 想起が device frame に寄る | `This is the LP itself, not a device mockup. No phone bezels, no browser chrome, no laptop frames.` |
| セクション高さが unbalanced（Hero 70%、Footer 20%） | 比率指定なし | LAYOUT に % 割当を明記（テンプレ通り） |
| 4 つ全部が独立ポスターになる（poster-designer） | persona 暴走 | `Only the hero is cinematic. Subsequent sections calm down into a readable grid.` を override で入れる |
| 全セクションが真っ黒で読めない（brutalist） | 反抗性の過剰解釈 | `Contrast must remain legible: body text > 7:1 against background.` |
| テープや回転が全要素にかかる（zine-kid） | 装飾過剰 | `Tape corners on 2-3 elements only, not on every tile.` |
| 「Lorem ipsum」「Your tagline here」が混入 | context を例示と誤解 | `No placeholder text. Every string is the provided Japanese. Any empty slot is a design error.` |
| moodboard を無視して自己流 | Read 指示が弱い | `Before you draw, OPEN and STUDY` を強制 + moodboard_block の各行を `- Open: <abs path>` 形式にする |

---

## 5. Python 実装例

`scripts/codex_mockup.py`（参考実装）

```python
"""Build and invoke the Codex LP mockup prompt."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.codex_image import generate
from scripts.designer_registry import Designer


# Designer-specific overrides live in one dict keyed by slug.
_DESIGNER_OVERRIDES: dict[str, str] = {
    "editorial-purist": """\
EXTRA GUIDANCE FOR editorial-purist:
- Paper-like cream background (#F4EFE6 — #EDE6D6). Body copy in dark
  brown-black, never pure #000.
- Hierarchy built from mincho sizes alone; no bold sans for emphasis.
- Generous vertical whitespace. No drop shadows, no soft glow cards.""",
    "zine-kid": """\
EXTRA GUIDANCE FOR zine-kid:
- Cream / off-white ground with subtle paper grain.
- Headings tilted -2 to +3 degrees. Masking tape on 2-3 elements max.
- 3-5 bright accents (fluoro yellow, coral, sky, mint). Hand-made,
  not childish — a design student's zine, not a kindergarten poster.""",
    "swiss-minimalist": """\
EXTRA GUIDANCE FOR swiss-minimalist:
- Strict 12-column baseline grid. 1px hairline rules between sections.
- ONE accent color. Uppercase kickers (~0.2em tracking). Mono numerals.
- No gradients, no texture, no illustration.""",
    "brutalist": """\
EXTRA GUIDANCE FOR brutalist:
- Stark black OR white, pick one. Accent: blood red (#FF0033) OR
  fluorescent yellow (#FFFF00), not both.
- Bebas Neue headings, Courier / JetBrains Mono body.
- 2-4px hard borders, intentional overlap, corner build-tags
  (e.g. "v1 — 2026.04"). No rounded corners > 2px.""",
    "poster-designer": """\
EXTRA GUIDANCE FOR poster-designer:
- Hero ≈ 45%, reads as a printed poster: one strong image/texture
  layer with ultra-condensed display type on top.
- Palette derived from the hero layer (analogous / duotone), 2 accents.
- Activities / CTA / Footer drop poster intensity and read as a calm,
  readable grid. Only hero is cinematic.""",
}


def _activities_block(activities: list[dict[str, str]]) -> str:
    lines = []
    for i, a in enumerate(activities[:4], start=1):
        lines.append(f"  {i}. {a['name']} — {a['description']}")
    return "\n".join(lines)


def _moodboard_block(paths: list[Path]) -> str:
    if not paths:
        return "  (no moodboard provided — rely on persona description only)"
    return "\n".join(f"  - Open: {p.resolve()}" for p in paths[:6])


def _fonts_list(fonts: list[str]) -> str:
    return "\n".join(f"  - {f}" for f in fonts) or "  - (use persona default)"


def build_codex_prompt(
    designer: Designer,
    team_ctx: dict[str, Any],
    output_path: Path,
) -> str:
    """Compose the full Codex prompt string for one mockup image."""
    return CODEX_MOCKUP_TEMPLATE.format(
        team_name=team_ctx["team_name"],
        team_tagline=team_ctx["team_tagline"],
        audience=team_ctx["audience"],
        unique_strength=team_ctx["unique_strength"],
        hero_copy=team_ctx["hero_copy"],
        main_cta=team_ctx["main_cta"],
        activities_block=_activities_block(team_ctx["activities"]),
        designer_display_name=designer.display_name,
        designer_name=designer.name,
        designer_persona_body=designer.persona_markdown,
        signature_fonts_list=_fonts_list(designer.signature_fonts),
        palette_rules=designer.palette_rules,
        motion_profile=designer.motion_profile,
        designer_specific_overrides=_DESIGNER_OVERRIDES.get(designer.name, ""),
        moodboard_block=_moodboard_block(designer.moodboard_paths()),
        output_path=str(output_path),
    )


def generate_mockup(
    designer: Designer,
    team_ctx: dict[str, Any],
    output_path: Path,
    timeout: int = 600,
) -> Path:
    """End-to-end: build prompt, call Codex, return saved PNG path."""
    prompt = build_codex_prompt(designer, team_ctx, output_path)
    # codex_image.generate() already wraps the "Generate ONE image / quit"
    # contract, but here the contract is embedded in the prompt itself,
    # so we pass the prompt as the full instruction and rely on Codex to
    # save to the path we baked in.
    return generate(
        prompt=prompt,
        aspect_ratio="9:16",
        output_path=output_path,
        timeout=timeout,
    )
```

### 呼び出し側（hp_generator から）

```python
from scripts.codex_mockup import generate_mockup
from scripts.designer_registry import get_designer

designer = get_designer(chosen_designer_slug)
team_ctx = {
    "team_name": interview["team_name"],
    "team_tagline": interview["tagline"],
    "audience": interview["audience"],
    "unique_strength": interview["unique_strength"],
    "hero_copy": interview["hero_copy"],
    "main_cta": interview["main_cta"],
    "activities": interview["activities"],  # [{name, description}]
}
mockup_path = Path("web/public/mockups") / f"{slug}.png"
generate_mockup(designer, team_ctx, mockup_path)

# Claude の 2nd turn にこの mockup を "visual target" として渡す:
#   "Here is a mockup you designed earlier: {mockup_path}.
#    Implement the MDX so the rendered page matches this composition."
```

---

## 6. チューニング運用メモ

- **まず 5 団体 × 5 persona = 25 枚**を生成して、§4 の失敗表をアップデートする
- 失敗が出たら対応策をプロンプト末尾の HARD CONSTRAINTS ではなく、**該当 persona の override** に入れる方が副作用が少ない
- `codex exec` は 1 枚あたり 40-90 秒かかる → 並列実行するなら `ThreadPoolExecutor(max_workers=3)` 程度（OpenAI 側の同時実行上限に注意）
- 生成した mockup は `web/public/mockups/<slug>.png` に保存 → Claude に絶対パスで渡す
- Claude が MDX を書く際、mockup を「拘束する仕様」ではなく「**合意された北極星**」として扱う（pixel-perfect は求めない）
