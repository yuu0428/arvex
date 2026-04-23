"""Vercel Blob への画像アップロードヘルパー。

`vercel blob put` CLI を subprocess で呼び出す方式。
SDK が Node だけなので、Python からは CLI 経由が最もシンプル。
"""
import os
import re
import subprocess
from pathlib import Path

from scripts import db  # noqa: F401 - .env のロード副作用のため

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
WEB_DIR = Path(__file__).parent.parent / "web"


def upload(local_path: Path, blob_pathname: str, force: bool = True) -> str:
    """ローカルファイルを Vercel Blob にアップロードし、公開 URL を返す。

    Args:
        local_path: アップロードするローカルファイル
        blob_pathname: Blob 内のパス (例: "p/demo-circle/hero.png")
        force: 既存ファイルを上書きするか
    """
    if not BLOB_TOKEN:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set")
    if not local_path.exists():
        raise FileNotFoundError(f"file not found: {local_path}")

    env = {**os.environ, "BLOB_READ_WRITE_TOKEN": BLOB_TOKEN}
    cmd = [
        "vercel", "blob", "put", str(local_path),
        "--pathname", blob_pathname,
        "--rw-token", BLOB_TOKEN,
    ]
    if force:
        cmd.append("--force")

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        env=env,
        cwd=str(WEB_DIR),   # vercel CLI は .vercel/project.json を見るので web/ から実行
        timeout=120,
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(f"vercel blob put failed (exit {result.returncode}):\n{combined}")

    # "Success! https://xxx.public.blob.vercel-storage.com/path" を抜き出す
    m = re.search(r"https://[\w\-.]+\.public\.blob\.vercel-storage\.com/\S+", combined)
    if not m:
        raise RuntimeError(f"could not parse blob URL from output:\n{combined}")
    return m.group(0)


def delete(url: str) -> None:
    env = {**os.environ, "BLOB_READ_WRITE_TOKEN": BLOB_TOKEN}
    subprocess.run(
        ["vercel", "blob", "del", url],
        capture_output=True, text=True, env=env, timeout=30,
    )
