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

from scripts import blob, db, link_explorer, web_enricher

STATE_PATH = Path(__file__).parent.parent / ".ig_state.json"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MAX_POSTS = 60  # 直近何投稿まで取るか（多いほど素材密度が上がる）
EXTERNAL_MAX_CHARS = 20000  # 外部ページ1本あたりの抽出上限
MAX_NOTE_BODIES = 6  # note 記事本文を fetch する件数（最新 N 本）
CAPTION_MAX_CHARS = 800  # 各投稿 caption の上限。長すぎると prompt token を食う
SCROLL_MAX_ITERATIONS = 30  # IG profile を最大何回スクロールするか
SCROLL_WAIT_MS = 1400  # スクロール後に新規 thumbnail が描画されるまでの待ち時間


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
    """(profile_picture_url, [{thumb_url, caption}, ...]) を返す。caption は空かも。

    IG profile は最初の ~12 件しか DOM に置かないので、目標件数に達するまで
    infinite scroll を発火させて遅延ロードする。
    """
    # プロフィール画像
    profile_pic = page.evaluate("""
        () => {
            const img = document.querySelector('header img');
            return img?.src || null;
        }
    """)

    # IG profile は virtualized scroll で画面外の thumbnail を DOM から外すので、
    # 一度の querySelectorAll では viewport 周辺の数十件しか取れない。
    # 累積は Python 側で href→item の dict として保持し、scroll するたびに新規分を merge する。
    collect_js = """
        () => {
            const items = [];
            const links = Array.from(document.querySelectorAll('main a[href*="/p/"], main a[href*="/reel/"]'));
            for (const a of links) {
                const img = a.querySelector('img');
                if (img?.src) {
                    items.push({ href: a.href, src: img.src, alt: img.alt || '' });
                }
            }
            return items;
        }
    """

    accumulated: dict[str, dict] = {}

    def harvest():
        batch = page.evaluate(collect_js) or []
        for item in batch:
            if item["href"] not in accumulated:
                accumulated[item["href"]] = item

    harvest()
    last_count = len(accumulated)
    stable_iters = 0

    for i in range(SCROLL_MAX_ITERATIONS):
        if len(accumulated) >= max_posts:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(SCROLL_WAIT_MS)
        harvest()
        if len(accumulated) == last_count:
            stable_iters += 1
            # 新規が 3 回連続で増えなくなったら最後まで読み切ったと判断して終了
            if stable_iters >= 3:
                break
        else:
            stable_iters = 0
            last_count = len(accumulated)

    thumbs = list(accumulated.values())[:max_posts]
    print(f"  scroll: collected {len(thumbs)} thumbs after {i+1} scroll iterations", flush=True)
    return profile_pic, thumbs


def _fetch_post_text(page: Page, post_url: str) -> str:
    """投稿ページの caption を抽出。CAPTION_MAX_CHARS で切り詰める。失敗時は空文字。"""
    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=10000)
        page.wait_for_timeout(700)
        txt = page.evaluate(
            """
            () => {
              const art = document.querySelector('article[role="presentation"]')
                       || document.querySelector('article')
                       || document.querySelector('main');
              if (!art) return '';
              return art.innerText || '';
            }
            """
        ) or ""
        if txt and len(txt.strip()) > 40:
            return txt.strip()[:CAPTION_MAX_CHARS]
        # fallback: og:description
        og = page.evaluate(
            "() => document.querySelector('meta[property=\"og:description\"]')?.content "
            "|| document.querySelector('meta[name=\"description\"]')?.content || ''"
        )
        return (og or "")[:CAPTION_MAX_CHARS]
    except Exception:
        return ""


def _fetch_captions(context, thumbs: list[dict]) -> None:
    """各投稿の caption を取得して thumbs[*]['caption'] に格納。失敗は空文字。

    Playwright sync API は同一 context 上での真の並列を許さないので serial。
    timeout 短め (10s) + sleep 短め (0.7s) で 1 件 1-2 秒に収まる想定。50 件 ≈ 1-2 分。
    """
    cur_page = context.new_page()
    try:
        for i, t in enumerate(thumbs):
            cap = _fetch_post_text(cur_page, t["href"])
            t["caption"] = cap
            if (i + 1) % 10 == 0 or (i + 1) == len(thumbs):
                print(f"  caption: {i+1}/{len(thumbs)} fetched", flush=True)
    finally:
        cur_page.close()


def _fetch_external_text(url: str, max_chars: int = EXTERNAL_MAX_CHARS) -> str:
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
        # caption は別 page で順次 fetch（grid の page を消費しないため）
        _fetch_captions(context, thumbs)

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


# ======================== Notable facts extraction ========================
# 目的: 素材中に実在する固有情報（人名・日付・イベント名・団体名・場所・引用）を
# 正規表現で抽出し、Claude に「発明するな、これを使え」と渡す。
# メニューではなく verified-from-source の候補リスト。
# 完全性より再現性優先: 偽陽性は OK、事実でないものを作らせないことが大事。

# 人名: 漢字 2-5 or カタカナ 2-8 + honorific or 役職
_NAME_HONORIFIC_RE = re.compile(
    r"([一-龥々]{1,5}(?:[一-龥々]|[ぁ-ん]){0,4}|[ァ-ヴー]{2,10})"
    r"(さん|氏|先生|監督|代表(?:理事|取締役)?|理事(?:長)?|会長|社長|教授|準教授|部長|校長)"
)
# 「〜」内の引用句（8〜80 文字くらい）
_QUOTE_RE = re.compile(r"「([^「」]{8,80})」")
# 日付
_DATE_PATTERNS = [
    re.compile(r"\b(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})日?"),
    re.compile(r"(\d{1,2})月(\d{1,2})日"),
]
# イベント・企画名: 『〜』 パターン, XXXまつり, XXXフェス, XXXプロジェクト
_EVENT_RE = re.compile(
    r"(『[^『』]{2,30}』|[一-龥ァ-ヴーA-Za-z々\d ]{2,20}(?:まつり|フェスティバル|フェス|プロジェクト|ワークショップ|シンポジウム|キャンペーン|コンテスト))"
)
# 団体名
_ORG_RE = re.compile(
    r"(NPO法人[一-龥ァ-ヴー々A-Za-z ]{1,20}|一般社団法人[一-龥ァ-ヴー々A-Za-z ]{1,20}|公益財団法人[一-龥ァ-ヴー々A-Za-z ]{1,20}|株式会社[一-龥ァ-ヴー々A-Za-z ]{1,20}|学生団体[一-龥ァ-ヴー々A-Za-z ]{1,20}|[一-龥ァ-ヴー々]{2,15}(?:協会|センター|財団|同盟|連合|研究会))"
)
# 地名・場所ヒント
_PLACE_RE = re.compile(
    r"([一-龥ァ-ヴー々]{2,10}(?:駅|市|町|村|区|県|府|都|町内|商店街|神社|寺|公園|城|町|温泉|温泉郷))"
)
# URL は別扱いで全取得
_URL_RE = re.compile(r"https?://[^\s　、。,)\]」』》]+")


def _dedupe_ordered(items: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        x = x.strip()
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
        if limit and len(out) >= limit:
            break
    return out


def extract_notable_facts(corpus: str) -> dict:
    """素材全文から固有情報候補を抽出。

    Claude に「これが素材に実在する情報。これ以外は発明しない」と示すための辞書。
    偽陽性は OK（Claude が適切に使い分ける）。見落としが一番まずい。
    """
    names = [m.group(0) for m in _NAME_HONORIFIC_RE.finditer(corpus)]
    quotes = [m.group(1) for m in _QUOTE_RE.finditer(corpus)]
    events = [m.group(1) for m in _EVENT_RE.finditer(corpus)]
    orgs = [m.group(1) for m in _ORG_RE.finditer(corpus)]
    places = [m.group(1) for m in _PLACE_RE.finditer(corpus)]
    urls = [m.group(0) for m in _URL_RE.finditer(corpus)]

    dates: list[str] = []
    for m in _DATE_PATTERNS[0].finditer(corpus):
        dates.append(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    for m in _DATE_PATTERNS[1].finditer(corpus):
        dates.append(f"{int(m.group(1))}月{int(m.group(2))}日")

    return {
        "names": _dedupe_ordered(names, limit=40),
        "quotes": _dedupe_ordered(quotes, limit=30),
        "dates": _dedupe_ordered(dates, limit=30),
        "events": _dedupe_ordered(events, limit=30),
        "orgs": _dedupe_ordered(orgs, limit=20),
        "places": _dedupe_ordered(places, limit=20),
        "urls": _dedupe_ordered(urls, limit=40),
    }


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
    published_content = link_explorer.explore(seeds, fetch_article_bodies=MAX_NOTE_BODIES)
    print(
        f"  {len(published_content['external_links'])} external links / "
        f"{len(published_content['articles'])} articles "
        f"({sum(1 for a in published_content['articles'] if a.get('body'))} with body)",
        flush=True,
    )

    # 5) IG-side notable_facts を抽出（anchor 用）
    ig_corpus_parts: list[str] = [profile.get("biography") or ""]
    for st in source_text:
        ig_corpus_parts.append(st.get("content") or "")
    for art in published_content.get("articles") or []:
        ig_corpus_parts.append(art.get("title") or "")
        ig_corpus_parts.append(art.get("description") or "")
        ig_corpus_parts.append(art.get("body") or "")
    ig_corpus = "\n".join(p for p in ig_corpus_parts if p)
    ig_notable_facts = extract_notable_facts(ig_corpus)

    # 6) Jina web 検索で entity-anchor 補強。
    #    IG の identity（団体名・大学・人名・イベント名・公式ドメイン）を anchor に取り、
    #    anchor が含まれない検索結果は同名他団体や無関係まとめサイトとして drop する。
    print("enriching with Jina web search ...", flush=True)
    web_enrichment = web_enricher.enrich(profile, ig_notable_facts, university)
    for r in web_enrichment["results"]:
        source_text.append({
            "type": "web_page",
            "url": r["url"],
            "content": r["content"],
        })

    # 7) final notable_facts: IG + web を合算して再抽出
    if web_enrichment["results"]:
        web_corpus = "\n".join(r["content"] for r in web_enrichment["results"])
        notable_facts = extract_notable_facts(ig_corpus + "\n" + web_corpus)
    else:
        notable_facts = ig_notable_facts
    notable_facts["_sources"] = {
        "web_queries": web_enrichment["queries_used"],
        "web_pages": [
            {"url": r["url"], "domain": r["domain"]}
            for r in web_enrichment["results"]
        ],
        "anchor_size": web_enrichment["anchor_size"],
    }
    print(
        f"  notable_facts: "
        f"{len(notable_facts['names'])} names, "
        f"{len(notable_facts['quotes'])} quotes, "
        f"{len(notable_facts['dates'])} dates, "
        f"{len(notable_facts['events'])} events, "
        f"{len(notable_facts['orgs'])} orgs, "
        f"{len(notable_facts['places'])} places",
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
        notable_facts=json.dumps(notable_facts, ensure_ascii=False),
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
