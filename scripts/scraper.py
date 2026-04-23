"""Playwright ベースの Instagram プロフィール取得 + 画像ダウンロード。

初回実行: ブラウザが headful で立ち上がる → ユーザーが手動ログイン → 自動検知
2回目以降: `.ig_state.json` のセッションを復元して headless で取得

プロフィール本文に加えて、プロフィール画像と直近の投稿サムネイルを収集し、
Vercel Blob に `p/<slug>/source/<n>.jpg` として上げ、URL + caption を
`orgs.source_assets` に JSON で保存する。

Usage:
    python -m scripts.scraper <instagram_handle> [university]
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

from scripts import blob, db, link_explorer

STATE_PATH = Path(__file__).parent.parent / ".ig_state.json"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MAX_POSTS = 8  # 直近何投稿まで取るか


def ensure_logged_in(timeout_sec: int = 600):
    """state.json が無ければ headful で起動し、ログイン完了を自動検知する。

    Instagram の sessionid cookie が発行されたらログイン済みと判定する。
    タイムアウト内に検知できなければ RuntimeError。
    """
    if STATE_PATH.exists():
        return
    print("Instagram のセッションがまだありません。")
    print("ブラウザを開きます。表示されたウィンドウでログインしてください（2FA も通常通り通してOK）。")
    print("ログイン完了は自動検知されるので、終わったらウィンドウを閉じずにそのまま待機してください。")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/")

        deadline = time.time() + timeout_sec
        last_report = 0
        while time.time() < deadline:
            cookies = context.cookies("https://www.instagram.com")
            if any(c["name"] == "sessionid" and c.get("value") for c in cookies):
                print("ログイン検知。セッションを保存します。", flush=True)
                break
            if time.time() - last_report > 15:
                remaining = int(deadline - time.time())
                print(f"  ...待機中（残り {remaining}s）", flush=True)
                last_report = time.time()
            time.sleep(2)
        else:
            browser.close()
            raise RuntimeError("ログインがタイムアウトしました")

        context.storage_state(path=str(STATE_PATH))
        browser.close()
    print(f"Session saved → {STATE_PATH}")


def _collect_images(page: Page, max_posts: int) -> tuple[str | None, list[dict]]:
    """(profile_picture_url, [{thumb_url, caption}, ...]) を返す。caption は空かも。"""
    # プロフィール画像
    profile_pic = page.evaluate("""
        () => {
            const img = document.querySelector('header img');
            return img?.src || null;
        }
    """)

    # 投稿グリッドのサムネイル
    thumbs = page.evaluate("""
        (n) => {
            const items = [];
            const links = Array.from(document.querySelectorAll('main article a[href*="/p/"], main a[href*="/p/"]'));
            for (const a of links) {
                const img = a.querySelector('img');
                if (img?.src) {
                    items.push({ href: a.href, src: img.src, alt: img.alt || '' });
                }
                if (items.length >= n) break;
            }
            return items;
        }
    """, max_posts)

    return profile_pic, thumbs


def _fetch_post_text(page: Page, post_url: str) -> str:
    """投稿ページの og:description（生のまま）を返す。

    加工は Claude 側に任せる方針なので、regex での切り出しはしない。
    失敗時は空文字。
    """
    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(0.8)
        og = page.evaluate(
            "() => document.querySelector('meta[property=\"og:description\"]')?.content "
            "|| document.querySelector('meta[name=\"description\"]')?.content || ''"
        )
        return og or ""
    except Exception:
        return ""


def _fetch_external_text(url: str, max_chars: int = 6000) -> str:
    """外部 URL（note / 公式サイト等）の本文テキストをざっくり取る。

    HTML から script/style を除去して text を抽出。Claude に読ませる用。
    失敗時は空文字。
    """
    try:
        resp = httpx.get(
            url,
            timeout=20,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return ""

    html = resp.text
    # タグの中身（script/style）を捨てる
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 残タグを除去
    text = re.sub(r"<[^>]+>", " ", html)
    # エンティティざっくり
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # 連続空白を詰める
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_profile(handle: str) -> dict:
    url = f"https://www.instagram.com/{handle}/"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(STATE_PATH),
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("header", timeout=20000)
        time.sleep(2)

        og_desc = page.evaluate(
            "() => document.querySelector('meta[property=\"og:description\"]')?.content || "
            "document.querySelector('meta[name=\"description\"]')?.content || ''"
        )
        og_title = page.evaluate(
            "() => document.querySelector('meta[property=\"og:title\"]')?.content || ''"
        )
        header_text = page.locator("header").inner_text()

        # プロフィールに複数リンクがある場合は "N more" ボタンで展開を試みる
        try:
            page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('header button, header [role=button]');
                    for (const b of buttons) {
                        const t = (b.textContent || '').toLowerCase();
                        if (/\\bmore\\b|もっと/.test(t)) { b.click(); return true; }
                    }
                    return false;
                }
            """)
            time.sleep(1.2)
        except Exception:
            pass

        # ヘッダー領域＋ダイアログ全体から外部 URL をかき集める
        raw_urls = page.evaluate("""
            () => {
                const currentHost = location.hostname;
                const nodes = document.querySelectorAll(
                    'header a[href], [role=dialog] a[href], main a[href]'
                );
                const out = new Set();
                for (const a of nodes) {
                    let href = a.href;
                    if (!href || href.startsWith('#') || href === 'about:blank') continue;
                    // Instagram のリダイレクトを剥がす
                    if (href.startsWith('https://l.instagram.com/')) {
                        try {
                            const u = new URL(href);
                            const real = u.searchParams.get('u');
                            if (real) { out.add(real); continue; }
                        } catch {}
                    }
                    if (href.includes(currentHost)) continue;
                    out.add(href);
                }
                return Array.from(out);
            }
        """) or []

        # bio テキストからも regex で URL を抜く
        bio_text = page.locator("header").inner_text()
        import re as _re
        text_urls = _re.findall(r'https?://[^\s　、。,)\]」]+', bio_text)
        # bio の "open.spotify.com/..." のような http を省略された形も拾う
        compact_urls = _re.findall(
            r'(?:open\.spotify\.com|note\.com|linktr\.ee|lit\.link|x\.com|twitter\.com|youtube\.com|youtu\.be|tiktok\.com|forms\.gle|forms\.google\.com)/[^\s　、。,)\]」]+',
            bio_text,
        )
        compact_urls = ["https://" + u for u in compact_urls]

        # 統合・重複除去（正規化は簡易）
        all_urls = []
        seen = set()
        for u in list(raw_urls) + compact_urls + text_urls:
            key = u.rstrip("/").split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            all_urls.append(u)
        external_urls = all_urls
        external_url = external_urls[0] if external_urls else None

        profile_pic, thumbs = _collect_images(page, MAX_POSTS)

        # 各投稿の caption（og:description 生文字列）を取る
        for t in thumbs:
            t["caption"] = _fetch_post_text(page, t["href"])

        browser.close()

    # 表示名
    full_name = handle
    m = re.search(r"^(.+?)\s*[\(（]\s*@", og_title or "")
    if m:
        full_name = m.group(1).strip()

    follower_count = 0
    media_count = 0
    m = re.search(r"([\d,]+)\s*Followers?", og_desc or "")
    if m:
        follower_count = int(m.group(1).replace(",", ""))
    m = re.search(r"([\d,]+)\s*Posts?", og_desc or "")
    if m:
        media_count = int(m.group(1).replace(",", ""))

    return {
        "handle": handle,
        "full_name": full_name,
        "biography": header_text,
        "external_url": external_url,
        "external_urls": external_urls,
        "follower_count": follower_count,
        "media_count": media_count,
        "profile_pic_url": profile_pic,
        "post_thumbs": thumbs,
    }


def _download_to_blob(src_url: str, dst_pathname: str) -> str | None:
    """Instagram の画像を DL → Blob にアップロード。失敗時 None。"""
    try:
        resp = httpx.get(src_url, timeout=30, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except Exception as e:
        print(f"  DL failed {src_url[:60]}...: {e}", flush=True)
        return None

    tmp_path = Path("/tmp") / Path(dst_pathname).name
    tmp_path.write_bytes(resp.content)
    try:
        url = blob.upload(tmp_path, dst_pathname, force=True)
        return url
    finally:
        tmp_path.unlink(missing_ok=True)


def collect_source_assets(handle: str, profile: dict) -> list[dict]:
    """プロフィール画像 + 投稿サムネを Blob に保存して metadata リストを返す。"""
    assets = []
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", handle).strip("-").lower()

    # profile picture
    if profile.get("profile_pic_url"):
        url = _download_to_blob(profile["profile_pic_url"], f"p/{slug}/source/profile.jpg")
        if url:
            assets.append({
                "type": "profile_pic",
                "url": url,
                "caption": profile.get("full_name") or handle,
            })

    # post thumbnails
    for i, t in enumerate(profile.get("post_thumbs") or []):
        blob_url = _download_to_blob(t["src"], f"p/{slug}/source/post_{i:02d}.jpg")
        if blob_url:
            assets.append({
                "type": "post_thumb",
                "url": blob_url,
                "caption": (t.get("caption") or "").strip(),
            })
    return assets


def _extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text or "")
    return m.group(0) if m else None


def scrape_and_save(handle: str, university: str | None = None) -> str:
    ensure_logged_in()
    print(f"fetching profile @{handle} ...", flush=True)
    profile = fetch_profile(handle)
    print(f"  name: {profile['full_name']}  posts: {profile['media_count']}  followers: {profile['follower_count']}", flush=True)
    print(f"  collected: profile_pic={bool(profile.get('profile_pic_url'))}, thumbs={len(profile.get('post_thumbs') or [])}", flush=True)

    print("downloading + uploading images to Blob ...", flush=True)
    source_assets = collect_source_assets(handle, profile)
    print(f"  saved {len(source_assets)} source assets to Blob", flush=True)

    # --- source_text を構築（生テキスト素材を束ねる）---
    source_text: list[dict] = []

    # 1) Instagram ヘッダーの全文
    source_text.append({
        "type": "ig_header",
        "url": f"https://www.instagram.com/{handle}/",
        "content": profile["biography"],
    })

    # 2) 各投稿の og:description（caption とメタ情報の生ブロック）
    for t in profile.get("post_thumbs") or []:
        cap = (t.get("caption") or "").strip()
        if cap:
            source_text.append({
                "type": "ig_post",
                "url": t.get("href"),
                "content": cap,
            })

    # 3) 外部URL（note / 公式サイト等）があれば本文を fetch
    ext = profile.get("external_url")
    if ext:
        print(f"fetching external page: {ext[:80]}", flush=True)
        ext_text = _fetch_external_text(ext)
        if ext_text:
            source_text.append({
                "type": "external_page",
                "url": ext,
                "content": ext_text,
            })
            print(f"  external text: {len(ext_text)} chars", flush=True)

    print(f"  collected {len(source_text)} source_text blocks", flush=True)

    # 4) 公開コンテンツの実URLを link_explorer で拾う（複数 seed 対応）
    print(f"exploring published content ...", flush=True)
    seeds = profile.get("external_urls") or ([ext] if ext else [])
    published_content = link_explorer.explore(seeds)
    print(
        f"  {len(published_content['external_links'])} external links / "
        f"{len(published_content['articles'])} articles",
        flush=True,
    )

    email = _extract_email(profile["biography"])
    org_id = db.insert_org(
        name=profile["full_name"] or handle,
        university=university,
        instagram=handle,
        email=email,
    )
    db.update_org(
        org_id,
        bio_summary=profile["biography"],
        source_assets=json.dumps(source_assets, ensure_ascii=False),
        source_text=json.dumps(source_text, ensure_ascii=False),
        published_content=json.dumps(published_content, ensure_ascii=False),
    )
    return org_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.scraper <instagram_handle> [university]")
        sys.exit(1)
    handle = sys.argv[1]
    university = sys.argv[2] if len(sys.argv) > 2 else None
    org_id = scrape_and_save(handle, university)
    org = db.get_org(org_id)
    assets = json.loads(org.get("source_assets") or "[]")
    print(f"\nSaved org: {org_id}")
    print(f"  name:          {org['name']}")
    print(f"  handle:        @{org['instagram']}")
    print(f"  email:         {org['email']}")
    print(f"  source assets: {len(assets)}")
    for a in assets[:4]:
        print(f"    - {a['type']}: {a['url']}")


if __name__ == "__main__":
    main()
