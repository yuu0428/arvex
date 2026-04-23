"""開発用: テスト団体を DB に投入して hp_generator を流すための種データを作る。

Usage:
    python -m scripts.seed_demo
    # 出力された org_id を使って:
    python -m scripts.hp_generator <org_id>
"""
import sys

from scripts import db


DEMO_ORGS = [
    {
        "name": "早稲田大学 デモサークル",
        "university": "早稲田大学",
        "instagram": "demo-circle",
        "category": "集客型",
        "bio_summary": "早稲田大学公認の音楽系サークル。週2回活動、初心者歓迎、年間150名所属。",
        "pain_points": "新歓シーズンの認知不足。他サークルとの差別化ポイントが伝わりづらい。",
    },
    {
        "name": "東京大学 国際ボランティアネットワーク",
        "university": "東京大学",
        "instagram": "utokyo-ivn",
        "category": "信用型",
        "bio_summary": "発展途上国の教育支援を行う学生団体。20年の活動実績、海外NGOと連携。",
        "pain_points": "活動の信頼性・実績を対外的に示す公式窓口が不足している。寄付・協賛の獲得機会を逃している。",
    },
    {
        "name": "慶應義塾大学 活版印刷工房",
        "university": "慶應義塾大学",
        "instagram": "keio-letterpress",
        "category": "信用型",
        "bio_summary": "手動活版印刷機を継承し、作品制作・研究を行うサークル。メンバー12名。",
        "pain_points": "ニッチな活動のため新歓での候補に上がりにくい。作品集を見せる場がない。",
    },
]


def main():
    # 既存 demo データをクリア（再実行しやすく）
    for org in DEMO_ORGS:
        handle = org["instagram"]
        existing = db.execute(
            "SELECT id FROM orgs WHERE instagram = ?", [handle]
        )
        if existing["response"]["result"]["rows"]:
            old_id = existing["response"]["result"]["rows"][0][0]["value"]
            db.execute("DELETE FROM outreach WHERE org_id = ?", [old_id])
            db.execute("DELETE FROM proposals WHERE org_id = ?", [old_id])
            db.execute("DELETE FROM orgs WHERE id = ?", [old_id])

    ids = []
    for org in DEMO_ORGS:
        org_id = db.insert_org(
            name=org["name"],
            university=org["university"],
            instagram=org["instagram"],
            email=None,
        )
        db.update_org(
            org_id,
            category=org["category"],
            bio_summary=org["bio_summary"],
            pain_points=org["pain_points"],
            status="analyzed",
        )
        ids.append((org_id, org["name"]))

    print("Seeded demo orgs:\n")
    for org_id, name in ids:
        print(f"  {org_id}  {name}")
    print("\nNext step:")
    print(f"  .venv/bin/python -m scripts.hp_generator {ids[0][0]}")


if __name__ == "__main__":
    main()
