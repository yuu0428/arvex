"""団体情報から 集客型/信用型 を判定し、課題仮説を生成。

Usage:
    python -m scripts.classifier <org_id>
"""
import sys

from scripts import claude_cli, db

MODEL = "opus"

SYSTEM_PROMPT = """あなたは学生団体・サークルのHP提案を行う arvex のアナリストです。
団体のInstagramプロフィール情報から、以下を判定してください。

### 分類軸（v0）
- **集客型**: 人を集めたい組織。サークル、部活、新歓・参加・募集を強化したい団体。
- **信用型**: 外部から信頼されたい組織。学生団体、ボランティア、地域連携、教育支援など。

### 出力形式（厳密なJSON、他のテキストは一切含めない）
{
  "category": "集客型" | "信用型",
  "confidence": 0.0〜1.0,
  "bio_summary": "活動内容の簡潔な要約（80字以内）",
  "pain_points": "HP制作で解決できそうな課題仮説（120字以内）"
}
"""


def classify(org: dict) -> dict:
    user_prompt = f"""団体名: {org['name']}
大学: {org.get('university') or '不明'}
Instagram: @{org.get('instagram') or ''}
プロフィール本文:
{org.get('bio_summary') or '(なし)'}
"""
    return claude_cli.call_json(SYSTEM_PROMPT, user_prompt, model=MODEL, timeout=180)


def classify_and_save(org_id: str) -> dict:
    org = db.get_org(org_id)
    if not org:
        raise ValueError(f"Org not found: {org_id}")
    result = classify(org)
    db.update_org(
        org_id,
        category=result["category"],
        bio_summary=result["bio_summary"],
        pain_points=result["pain_points"],
        status="analyzed",
    )
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.classifier <org_id>")
        sys.exit(1)
    org_id = sys.argv[1]
    result = classify_and_save(org_id)
    print(f"Org {org_id} classified:")
    print(f"  category:    {result['category']} (confidence={result['confidence']})")
    print(f"  bio_summary: {result['bio_summary']}")
    print(f"  pain_points: {result['pain_points']}")


if __name__ == "__main__":
    main()
