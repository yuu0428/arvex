"""各デザイナーに愛するサイトを 5-7 個聞き、Playwright でスクショして moodboard/ に保存する。

一回だけ走らせれば OK。再実行は既存の favorites.json を尊重する（上書きしない）。
favorites.json を手動で編集 → `python -m scripts.collect_moodboards <designer>` で再収集も可。

Usage:
    python -m scripts.collect_moodboards              # 全員
    python -m scripts.collect_moodboards brutalist    # 1 人だけ
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts import claude_cli, designer_registry


FAVORITES_SYSTEM_PROMPT = """あなたは以下のデザイナーペルソナです。自分が**心から好き**な実在のウェブサイトを 5-7 個挙げてください。

### あなたのペルソナ

{persona}

### ルール

- 実在する URL のみ（https://... で始まる本物）
- **自分のペルソナを強く体現している**サイトを選ぶ（他のペルソナでも共有されそうな generic な名作は避ける）
- 大手サービス (Apple, Stripe, Vercel 等) は generic すぎるので**避ける**
- editorial / independent / studio / artist portfolio / zine / 美術館 / 雑誌 / NPO など、**個性の強い**サイトを優先
- JP サイトでも海外サイトでもよい

### 出力形式（JSON 配列、前置き/後書き一切なし）

```json
[
  {{"url": "https://...", "why": "選んだ理由（1 文で）"}},
  ...
]
```
"""


def ask_designer_for_favorites(designer: designer_registry.Designer) -> list[dict]:
    user_prompt = "あなたが本当に好きなウェブサイトを 5-7 個、JSON 配列で出してください。"
    system_prompt = FAVORITES_SYSTEM_PROMPT.format(persona=designer.persona_markdown)
    raw = claude_cli.call_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="opus",
    )
    # 裸の JSON 配列を拾う
    import re
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        raise ValueError(f"no JSON array in response:\n{raw[:600]}")
    return json.loads(m.group(0))


def screenshot_sites(urls: list[str], out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for i, url in enumerate(urls):
            try:
                ctx = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                    ),
                )
                page = ctx.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1500)
                path = out_dir / f"{i+1:02d}.png"
                page.screenshot(path=str(path), full_page=False)  # above the fold のみ、軽量
                paths.append(path)
                print(f"  [{i+1}/{len(urls)}] {url[:80]} → {path.name}", flush=True)
                ctx.close()
            except Exception as e:
                print(f"  [{i+1}/{len(urls)}] FAILED {url[:80]}: {e}", flush=True)
                try:
                    ctx.close()
                except Exception:
                    pass
        browser.close()
    return paths


def collect_for(designer: designer_registry.Designer, force: bool = False) -> None:
    print(f"\n=== {designer.name} ({designer.display_name}) ===", flush=True)
    favs_path = designer.favorites_path
    if favs_path.exists() and not force:
        print(f"  favorites.json exists, using it", flush=True)
        favorites = json.loads(favs_path.read_text(encoding="utf-8"))
    else:
        print(f"  asking persona for favorites ...", flush=True)
        favorites = ask_designer_for_favorites(designer)
        favs_path.write_text(json.dumps(favorites, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  saved {len(favorites)} favorites to {favs_path.name}", flush=True)

    urls = [f["url"] for f in favorites if f.get("url", "").startswith("http")]
    if not urls:
        print(f"  no valid URLs to screenshot", flush=True)
        return

    print(f"  screenshotting {len(urls)} sites ...", flush=True)
    screenshot_sites(urls, designer.moodboard_dir)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    force = "--force" in sys.argv

    designers = designer_registry.load_designers()
    if target:
        designers = [d for d in designers if d.name == target]
        if not designers:
            print(f"designer '{target}' not found", file=sys.stderr)
            return 1

    for d in designers:
        collect_for(d, force=force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
