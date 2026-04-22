"""提案HPのURLを Instagram DM / メールで送付。

Usage:
    python -m scripts.outreach <org_id> <proposal_id> [--channel instagram|email]
"""
import argparse
import os
import random
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv

from scripts import db
from scripts.scraper import get_client as ig_client

load_dotenv()

DM_TEMPLATE = """{name} の皆さま

はじめまして、学生団体向けHP制作の arvex です。
{name} の活動をInstagramで拝見し、もし公式HPがあれば{benefit}につながると思い、
試しに1枚のたたき台HPを作りました。

{url}

よろしければご覧いただき、ご要望をフォームで教えてください。
10秒ほどで終わります。"""

EMAIL_SUBJECT = "【arvex】{name} の提案HPを作りました"


def _message_for(org: dict, url: str) -> str:
    if org.get("category") == "信用型":
        benefit = "活動への信頼獲得"
    else:
        benefit = "新歓・参加募集の強化"
    return DM_TEMPLATE.format(name=org["name"], benefit=benefit, url=url)


def send_instagram_dm(org: dict, message: str) -> bool:
    cl = ig_client()
    user_id = cl.user_id_from_username(org["instagram"])
    # フォロー → ランダム待機 → DM
    cl.user_follow(user_id)
    time.sleep(random.uniform(30, 90))
    cl.direct_send(text=message, user_ids=[int(user_id)])
    return True


def send_email(org: dict, message: str) -> bool:
    if not org.get("email"):
        raise ValueError("No email address for org")
    msg = MIMEText(message)
    msg["Subject"] = EMAIL_SUBJECT.format(name=org["name"])
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = org["email"]

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
    return True


def send(org_id: str, proposal_id: str, channel: str, base_url: str) -> str:
    org = db.get_org(org_id)
    if not org:
        raise ValueError(f"Org not found: {org_id}")

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
    if not row:
        raise ValueError(f"Proposal not found: {proposal_id}")

    url = f"{base_url.rstrip('/')}/p/{row['slug']}"
    message = _message_for(org, url)

    if channel == "instagram":
        if not org.get("instagram"):
            raise ValueError("No instagram handle")
        send_instagram_dm(org, message)
    elif channel == "email":
        send_email(org, message)
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    sent_at = datetime.now().isoformat()
    outreach_id = db.insert_outreach(org_id=org_id, proposal_id=proposal_id, channel=channel, sent_at=sent_at)
    return outreach_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("org_id")
    parser.add_argument("proposal_id")
    parser.add_argument("--channel", choices=["instagram", "email"], required=True)
    parser.add_argument("--base-url", default=os.environ.get("ARVEX_BASE_URL", "http://localhost:3000"))
    args = parser.parse_args()

    outreach_id = send(args.org_id, args.proposal_id, args.channel, args.base_url)
    print(f"Outreach sent: {outreach_id} ({args.channel})")


if __name__ == "__main__":
    main()
