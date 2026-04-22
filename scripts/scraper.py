"""Instagram プロフィール取得 → orgs テーブルに保存。

Usage:
    python -m scripts.scraper <instagram_handle> [university]
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client

from scripts import db

load_dotenv()

SESSION_PATH = Path(__file__).parent.parent / ".ig_session.json"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def get_client() -> Client:
    username = os.environ["IG_USERNAME"]
    password = os.environ["IG_PASSWORD"]
    cl = Client()
    if SESSION_PATH.exists():
        cl.load_settings(SESSION_PATH)
    cl.login(username, password)
    cl.dump_settings(SESSION_PATH)
    return cl


def fetch_profile(handle: str) -> dict:
    cl = get_client()
    user_id = cl.user_id_from_username(handle)
    info = cl.user_info(user_id)
    return {
        "handle": handle,
        "full_name": info.full_name,
        "biography": info.biography or "",
        "external_url": str(info.external_url) if info.external_url else None,
        "follower_count": info.follower_count,
        "media_count": info.media_count,
        "is_private": info.is_private,
    }


def extract_email(bio: str) -> str | None:
    m = EMAIL_RE.search(bio or "")
    return m.group(0) if m else None


def scrape_and_save(handle: str, university: str | None = None) -> str:
    profile = fetch_profile(handle)
    email = extract_email(profile["biography"])
    org_id = db.insert_org(
        name=profile["full_name"] or handle,
        university=university,
        instagram=handle,
        email=email,
    )
    db.update_org(org_id, bio_summary=profile["biography"])
    return org_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.scraper <instagram_handle> [university]")
        sys.exit(1)
    handle = sys.argv[1]
    university = sys.argv[2] if len(sys.argv) > 2 else None
    org_id = scrape_and_save(handle, university)
    org = db.get_org(org_id)
    print(f"Saved org: {org_id}")
    print(f"  name:      {org['name']}")
    print(f"  email:     {org['email']}")
    print(f"  bio:       {org['bio_summary'][:80] if org['bio_summary'] else ''}...")


if __name__ == "__main__":
    main()
