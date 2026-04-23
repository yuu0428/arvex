# Codex による画像生成

## 基本コマンド

```bash
codex exec -s workspace-write -c 'shell_environment_policy.inherit=all' "<プロンプト>"
```

## 必要な条件

- `OPENAI_API_KEY` がシェル環境に設定されていること
- Codex CLI が最新版であること（`npm install -g @openai/codex@latest`）

## オプション解説

| オプション | 意味 |
|---|---|
| `-s workspace-write` | プロジェクトディレクトリへの書き込みを許可 |
| `-c 'shell_environment_policy.inherit=all'` | `OPENAI_API_KEY` 等のシェル環境変数を引き継ぐ |

## 実行例（HP 用画像3枚生成）

```bash
codex exec -s workspace-write -c 'shell_environment_policy.inherit=all' "Generate 3 images and save them to /Users/yura/arvex/web/public/brand/

1. hero.png (16:9 landscape): Minimal dark studio workspace, matte black desk with open MacBook displaying a clean white website wireframe, soft directional lighting, monochromatic dark palette, editorial product photography, Japanese minimalism

2. service.png (1:1): Two Japanese university students collaborating at a bright modern cafe, one pointing at laptop screen showing a minimalist website, soft natural window light, warm editorial photography

3. abstract.png (1:1): Abstract geometric grid lines representing web page structure, ultra-thin white lines on near-black background, subtle 3D depth, minimal tech aesthetic, dark mode"
```

## 出力結果

- `hero.png` — 1672×941（16:9）
- `service.png` — 1254×1254（1:1）
- `abstract.png` — 1254×1254（1:1）

## ハマった点

- `-s workspace-write` なしだと read-only サンドボックスでファイル保存が `Operation not permitted` になる
- `shell_environment_policy.inherit=all` なしだと `OPENAI_API_KEY` が渡らず画像生成が失敗する
- Codex CLI が古いと `thread/name/set` エラーが出る → `npm install -g @openai/codex@latest` で更新
- Codex は cwd 以下にしか書けないので、絶対パスで保存先を指定する
- プロンプトに "Do not ask questions. Save to the exact path. Quit after saving." を入れないと対話モードに入ってしまう事がある

## Python から呼ぶパターン（`scripts/codex_image.py`）

```python
import os
import subprocess
from pathlib import Path

def generate(prompt: str, aspect_ratio: str, output_path: Path, timeout: int = 300) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    instruction = f"""Generate exactly ONE image and save it to {output_path} as PNG.

Aspect ratio: {aspect_ratio}
Prompt: {prompt}

Do not ask questions. Do not generate multiple images. Save to the exact path above. Quit after saving."""

    cmd = [
        "codex", "exec",
        "-s", "workspace-write",
        "-c", "shell_environment_policy.inherit=all",
        instruction,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), timeout=timeout)
    if not output_path.exists():
        raise RuntimeError(f"Codex didn't save image: {result.stdout[-1500:]}")
    return output_path
```

## 並列化

Codex は呼び出しごとに別プロセスで OpenAI API を叩くので、複数枚を `ThreadPoolExecutor` で並列にできる。実測で4枚を逐次10分 → 並列3分まで短縮。

```python
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=len(specs)) as pool:
    results = list(pool.map(lambda s: gen_one(s), specs))
```

CLI 起動のオーバーヘッドと OpenAI 側のレート制限の両方がボトルネックになり得るので、`max_workers` は画像枚数と同数くらいが実用的な上限。
