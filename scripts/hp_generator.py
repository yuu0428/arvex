"""団体情報から Next.js 提案HPページを生成し、画像を Gemini で作る。

Usage:
    python -m scripts.hp_generator <org_id>

生成物:
    web/app/p/<slug>/page.tsx
    web/public/p/<slug>/*.png  (Geminiで生成)
    DBの proposals レコード
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from scripts import db

load_dotenv()

WEB_ROOT = Path(__file__).parent.parent / "web"
MODEL = "claude-opus-4-7"
PROPOSAL_TTL_DAYS = 10

SYSTEM_PROMPT = """あなたは arvex の提案HP生成エージェントです。
学生団体の情報から、Next.js 15 App Router 向けの提案用デモHPを1ページ分生成してください。

### 制約
- 出力は TypeScript (TSX) の1ファイル。React Server Component として動く。
- Tailwind CSS のみでスタイリング（他のCSSライブラリは使わない）。
- `<img src="/p/{slug}/xxx.png">` 形式で画像を参照。絶対パス。
- 情報過多を避け、目的（集客型なら参加、信用型なら信用）に最短で到達する構成。
- CTA は Google フォーム（後で注入する `{{FORM_URL}}` を href に）。
- Claude の自由な判断で構成・セクション数・トーンを決めてよい。ただし1ページで完結すること。

### 出力形式（厳密なJSON、他のテキスト一切なし）
{
  "page_tsx": "<TSXファイル全文>",
  "images": [
    {"filename": "hero.png", "prompt": "画像生成プロンプト（英語推奨）", "aspect_ratio": "16:9"}
  ]
}
"""


def slugify(handle: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", handle or "org").strip("-").lower()
    return s or "org"


def generate_page(org: dict, slug: str) -> dict:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_prompt = f"""### 団体情報
名前: {org['name']}
大学: {org.get('university') or '不明'}
分類: {org.get('category') or '未分類'}
活動概要: {org.get('bio_summary') or ''}
課題仮説: {org.get('pain_points') or ''}
Instagram: @{org.get('instagram') or ''}

### 生成対象のslug
{slug}

上記を踏まえて提案HPのTSXと必要な画像スペックを出力してください。
"""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1].rsplit("\n", 1)[0]
    return json.loads(text)


def generate_image(prompt: str, aspect_ratio: str, out_path: Path):
    """Gemini API で画像生成して out_path に保存。"""
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    # 画像生成モデル（2026時点）
    model = genai.GenerativeModel("imagen-3.0-generate-002")
    response = model.generate_content(
        prompt,
        generation_config={"aspect_ratio": aspect_ratio},
    )
    # 実装は Google SDK 版に依存。バイト列として受け取って書き出す。
    image_bytes = response.candidates[0].content.parts[0].inline_data.data
    out_path.write_bytes(image_bytes)


def write_page_files(slug: str, page_tsx: str, images: list[dict]):
    page_dir = WEB_ROOT / "app" / "p" / slug
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "page.tsx").write_text(page_tsx)

    img_dir = WEB_ROOT / "public" / "p" / slug
    img_dir.mkdir(parents=True, exist_ok=True)
    for spec in images:
        out = img_dir / spec["filename"]
        try:
            generate_image(spec["prompt"], spec.get("aspect_ratio", "16:9"), out)
            print(f"  image: {out.name} generated")
        except Exception as e:
            print(f"  image: {out.name} SKIPPED ({e})")


def generate_and_save(org_id: str, form_url: str | None = None) -> str:
    org = db.get_org(org_id)
    if not org:
        raise ValueError(f"Org not found: {org_id}")

    slug = slugify(org.get("instagram") or org_id[:8])
    result = generate_page(org, slug)
    page_tsx = result["page_tsx"].replace("{{FORM_URL}}", form_url or "#")

    write_page_files(slug, page_tsx, result.get("images", []))

    expires_at = (datetime.now() + timedelta(days=PROPOSAL_TTL_DAYS)).isoformat()
    proposal_id = db.insert_proposal(org_id=org_id, slug=slug, expires_at=expires_at)
    db.update_proposal(proposal_id, form_url=form_url, vercel_url=f"/p/{slug}")
    db.update_org(org_id, status="proposal_sent")
    return proposal_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.hp_generator <org_id> [form_url]")
        sys.exit(1)
    org_id = sys.argv[1]
    form_url = sys.argv[2] if len(sys.argv) > 2 else None
    proposal_id = generate_and_save(org_id, form_url)
    print(f"Proposal generated: {proposal_id}")


if __name__ == "__main__":
    main()
