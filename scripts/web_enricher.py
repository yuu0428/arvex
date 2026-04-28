"""DuckDuckGo HTML 検索 + Jina Reader で web 由来情報を補強する。

API key 不要の完全無料構成。
- 検索: https://html.duckduckgo.com/html/ を bs4 でパース
- 本文取得: https://r.jina.ai/<URL> で Markdown 化（s.jina.ai は認証必須化したので使わない）

IG corpus を「真実の anchor」として、検索結果を entity-anchor フィルタにかけ、
同名他団体・無関係まとめサイトを除外したうえで corpus に追加する。

設計原則:
- IG → anchor → web の sequential（並列だと anchor 無しで noise 流入）
- 検索クエリ間は並列、Reader fetch も並列
- title+snippet で**早期**フィルタ → 通過した URL だけ Reader fetch（無駄な fetch を抑制）
- すべての通信失敗は空配列に集約 → IG だけで HP 生成は継続できる
"""
import asyncio
import os
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

DDG_BASE = "https://html.duckduckgo.com/html/"
JINA_READER_BASE = "https://r.jina.ai/"

DDG_TIMEOUT = 20
READER_TIMEOUT = 30
MAX_DDG_RESULTS_PER_QUERY = 8
MAX_KEPT_PAGES = 8
WEB_CONTENT_MAX_CHARS = 6000

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MIN_ANCHOR_LEN = 3
# 一般語すぎて同名他団体除去に効かない anchor は捨てる
ANCHOR_STOPWORDS = {
    "東京", "学生", "団体", "サークル", "活動", "学園", "大学", "公演",
    "プロジェクト", "イベント", "メンバー", "代表", "会長", "副会長",
    "ニュース", "記事", "公式", "応援",
}
# IG / 一般 SNS / フォーム / DDG 自身は fetch しても新規情報が薄いので除外
SKIP_DOMAINS = {
    "instagram.com", "twitter.com", "x.com", "facebook.com",
    "tiktok.com", "youtube.com", "youtu.be",
    "linktr.ee", "lit.link", "forms.gle", "forms.google.com",
    "duckduckgo.com",
}


def _normalize(s: str) -> str:
    return s.strip().lower().replace(" ", "").replace("　", "")


def _reader_headers() -> dict:
    h = {"X-Return-Format": "markdown"}
    api_key = os.environ.get("JINA_API_KEY")
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _unwrap_ddg_url(href: str) -> str:
    """DDG が結果 URL を /l/?uddg=... で包む場合があるので生 URL を取り出す。"""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href and "uddg=" in href:
        try:
            qs = parse_qs(urlparse(href).query)
            real = qs.get("uddg", [""])[0]
            return real or href
        except Exception:
            return href
    return href


def build_anchor_set(profile: dict, ig_notable_facts: dict, university: str | None) -> set[str]:
    """IG corpus から「この団体の identity」を表す anchor を集める。

    web ページにこのうち 1 つも含まれない場合は同名他団体や無関係ページと判定して drop する。
    """
    anchors: set[str] = set()

    full_name = (profile.get("full_name") or "").strip()
    handle = (profile.get("handle") or "").strip()
    if full_name:
        anchors.add(_normalize(full_name))
    if handle:
        anchors.add(_normalize(handle))
    if university:
        anchors.add(_normalize(university))

    for name in ig_notable_facts.get("names", [])[:15]:
        anchors.add(_normalize(name))

    for ev in ig_notable_facts.get("events", [])[:10]:
        cleaned = ev.strip("『』 ")
        if len(cleaned) >= MIN_ANCHOR_LEN:
            anchors.add(_normalize(cleaned))

    for url in ig_notable_facts.get("urls", []):
        try:
            host = (urlparse(url).hostname or "").lower()
            if host and not any(bad in host for bad in SKIP_DOMAINS):
                anchors.add(host)
        except Exception:
            pass

    return {a for a in anchors if len(a) >= MIN_ANCHOR_LEN and a not in ANCHOR_STOPWORDS}


def generate_queries(profile: dict, university: str | None) -> list[str]:
    name = (profile.get("full_name") or profile.get("handle") or "").strip()
    if not name:
        return []
    raw = [
        name,
        f"{name} {university}" if university else None,
        f"{name} 公演",
        f"{name} インタビュー",
        f"{name} note",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for q in raw:
        if not q:
            continue
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out[:5]


async def _ddg_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    """DDG HTML endpoint を POST して上位 N 件を返す。"""
    try:
        resp = await client.post(
            DDG_BASE,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=DDG_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  ddg query failed [{query}]: {e}", flush=True)
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    out: list[dict] = []
    for r in soup.select("div.result"):
        a = r.select_one("a.result__a")
        if not a:
            continue
        href = _unwrap_ddg_url(a.get("href") or "")
        if not href:
            continue
        title = a.get_text(strip=True)
        snip_el = r.select_one(".result__snippet")
        snippet = snip_el.get_text(strip=True) if snip_el else ""
        out.append({
            "query": query,
            "url": href,
            "title": title,
            "snippet": snippet,
        })
        if len(out) >= MAX_DDG_RESULTS_PER_QUERY:
            break
    return out


async def _reader_fetch(client: httpx.AsyncClient, url: str) -> str:
    """r.jina.ai 経由でページを Markdown 取得。失敗時は空文字。"""
    try:
        resp = await client.get(
            JINA_READER_BASE + url,
            headers=_reader_headers(),
            timeout=READER_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.text or ""
    except Exception as e:
        print(f"  reader fetch failed [{url[:60]}]: {e}", flush=True)
        return ""


def _passes_anchor(text: str, anchors: set[str]) -> bool:
    if not text or not anchors:
        return False
    norm = _normalize(text)
    return any(a in norm for a in anchors if a)


def _early_filter(results: list[dict], anchors: set[str]) -> list[dict]:
    """title + snippet で先に絞る。Reader fetch (1〜3s/件) の前に無駄打ちを減らす。"""
    seen_urls: set[str] = set()
    kept: list[dict] = []
    for r in results:
        url = r.get("url") or ""
        if not url:
            continue
        try:
            domain = (urlparse(url).hostname or "").lower()
        except Exception:
            domain = ""
        if any(bad in domain for bad in SKIP_DOMAINS):
            continue

        norm_url = url.rstrip("/").split("?")[0]
        if norm_url in seen_urls:
            continue

        haystack = (r.get("title") or "") + "\n" + (r.get("snippet") or "")
        if not _passes_anchor(haystack, anchors):
            continue

        seen_urls.add(norm_url)
        kept.append({**r, "domain": domain})
    return kept


async def _enrich_async(profile: dict, ig_notable_facts: dict, university: str | None) -> dict:
    anchors = build_anchor_set(profile, ig_notable_facts, university)
    queries = generate_queries(profile, university)
    if not anchors or not queries:
        print("  web enrichment skipped (no anchors or queries)", flush=True)
        return {"queries_used": queries, "results": [], "anchor_size": len(anchors)}

    print(f"  ddg queries: {queries}", flush=True)
    sample = sorted(anchors)[:8]
    print(f"  anchors ({len(anchors)}): {sample}{'...' if len(anchors) > 8 else ''}", flush=True)

    async with httpx.AsyncClient() as client:
        search_tasks = [_ddg_search(client, q) for q in queries]
        batches = await asyncio.gather(*search_tasks, return_exceptions=True)
        raw: list[dict] = []
        for b in batches:
            if isinstance(b, Exception):
                continue
            raw.extend(b)
        print(f"  ddg raw results: {len(raw)} hits", flush=True)

        candidates = _early_filter(raw, anchors)
        print(f"  after early anchor filter: {len(candidates)} candidates", flush=True)
        candidates = candidates[:MAX_KEPT_PAGES]
        if not candidates:
            return {"queries_used": queries, "results": [], "anchor_size": len(anchors)}

        fetch_tasks = [_reader_fetch(client, c["url"]) for c in candidates]
        contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    kept: list[dict] = []
    for c, content in zip(candidates, contents):
        if isinstance(content, Exception) or not content:
            continue
        kept.append({
            "url": c["url"],
            "title": c.get("title") or "",
            "domain": c.get("domain") or "",
            "content": content[:WEB_CONTENT_MAX_CHARS],
            "matched_query": c.get("query") or "",
        })
    print(f"  fetched & kept: {len(kept)} pages", flush=True)
    return {"queries_used": queries, "results": kept, "anchor_size": len(anchors)}


def enrich(profile: dict, ig_notable_facts: dict, university: str | None) -> dict:
    """IG profile + IG-side notable_facts を入力に DDG 検索 + Reader 取得。

    Returns:
        {
            "queries_used": [...],
            "results": [{"url", "title", "domain", "content", "matched_query"}, ...],
            "anchor_size": int,
        }
    """
    try:
        return asyncio.run(_enrich_async(profile, ig_notable_facts, university))
    except Exception as e:
        print(f"  web enrichment failed: {e}", flush=True)
        return {"queries_used": [], "results": [], "anchor_size": 0}
