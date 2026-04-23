"""団体の外部リンクを起点に、公開コンテンツの実 URL をかき集める。

- linktr.ee / lit.link を展開して全外部リンクを取る
- note のユーザーページを受け取ったら RSS を読んで記事一覧を取る

Usage:
    result = link_explorer.explore(seed_url)
    # result = {external_links: [...], articles: [...], episodes: [...]}
"""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _get(url: str, timeout: int = 20) -> httpx.Response | None:
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"},
            follow_redirects=True,
            timeout=timeout,
        )
        r.raise_for_status()
        return r
    except Exception:
        return None


# ================ linktr.ee / lit.link expansion ================

def expand_linktree(url: str) -> list[dict]:
    """linktr.ee / lit.link のページから外部リンクを全部抜く。"""
    r = _get(url)
    if not r:
        return []
    html = r.text
    base_host = re.sub(r"^https?://([^/]+).*$", r"\1", url)

    out: list[dict] = []
    seen = set()
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        u = m.group(1)
        if base_host in u:
            continue
        # Skip tracking scripts / analytics etc.
        if any(bad in u for bad in ("google-analytics.com", "googletagmanager", "facebook.com/tr")):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append({"url": u})
    return out


# ================ note.com articles via RSS ================

def fetch_note_articles(user_url: str) -> list[dict]:
    """note の RSS から記事一覧を取る。user_url は https://note.com/{user} 形式でも記事URLでも可。"""
    m = re.search(r"^https?://note\.com/([^/?#]+)", user_url)
    if not m:
        return []
    user = m.group(1)
    rss_url = f"https://note.com/{user}/rss"
    r = _get(rss_url)
    if not r:
        return []
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return []

    items: list[dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        # description は HTML が入るのでタグ除去
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()[:400]
        if title and link:
            items.append({
                "platform": "note",
                "title": title,
                "url": link,
                "published_at": pub,
                "description": desc,
            })
    return items


def fetch_note_article_body(url: str, max_chars: int = 8000) -> str:
    """note 記事ページから本文テキストを取得。

    note は article 本文を `<div class="note-common-styles__textnote-body">` か、
    最近のレイアウトだと `<article>` 内の段落にまとめている。
    確実な path が見つからない場合 article の innerText を使う。失敗時は空文字。
    """
    r = _get(url, timeout=25)
    if not r:
        return ""
    html = r.text
    # script/style 除去
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # article タグだけ抽出（noteの記事本体）
    m = re.search(r"<article[^>]*>(.*?)</article>", html, flags=re.DOTALL | re.IGNORECASE)
    body_html = m.group(1) if m else html
    # タグ除去
    text = re.sub(r"<[^>]+>", " ", body_html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# ================ classification ================

def classify(url: str) -> str:
    """URL のプラットフォームを粗く分類。"""
    u = url.lower()
    if "linktr.ee" in u or "lit.link" in u:
        return "linktree"
    if "note.com/" in u:
        return "note"
    if "open.spotify.com/show" in u:
        return "spotify_show"
    if "open.spotify.com/episode" in u:
        return "spotify_episode"
    if "instagram.com" in u:
        return "instagram"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "twitter.com" in u or "x.com" in u:
        return "x"
    if "tiktok.com" in u:
        return "tiktok"
    if "forms.google.com" in u or "forms.gle" in u:
        return "form"
    if "peatix.com" in u:
        return "peatix"
    if any(k in u for k in ("@", "mailto:")):
        return "email"
    return "web"


# ================ main orchestration ================

def explore(seed_urls: str | list[str] | None, fetch_article_bodies: int = 0) -> dict:
    """seed URL 群（プロフィール bio に書かれた外部リンク）から辿れる公開コンテンツを集める。

    - fetch_article_bodies: 最新 N 本の記事本文を fetch して `body` フィールドに入れる。
      0 なら本文 fetch なし。

    戻り値:
        {
          "external_links": [ {url, platform}, ... ],
          "articles":       [ {platform, title, url, published_at, description, body?}, ... ]
        }
    """
    empty = {"external_links": [], "articles": []}
    if not seed_urls:
        return empty
    if isinstance(seed_urls, str):
        seed_urls = [seed_urls]

    # Step 1: seed URL 全部を links に入れる + linktree は展開
    links: list[dict] = []
    for u in seed_urls:
        links.append({"url": u})
        if classify(u) == "linktree":
            links.extend(expand_linktree(u))

    # Step 2: 分類
    classified: list[dict] = []
    seen = set()
    for l in links:
        u = l["url"]
        if u in seen:
            continue
        seen.add(u)
        classified.append({"url": u, "platform": classify(u)})

    # Step 3: プラットフォーム別取得（note のみ。Spotify は扱わない）
    articles: list[dict] = []
    for l in classified:
        if l["platform"] == "note":
            articles.extend(fetch_note_articles(l["url"]))

    # Step 4: 本文 fetch（最新 N 本）
    if fetch_article_bodies > 0 and articles:
        for a in articles[:fetch_article_bodies]:
            if a.get("platform") == "note" and a.get("url"):
                body = fetch_note_article_body(a["url"])
                if body:
                    a["body"] = body

    return {
        "external_links": classified,
        "articles": articles,
    }


if __name__ == "__main__":
    import json
    import sys
    seed = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(explore(seed), ensure_ascii=False, indent=2))
