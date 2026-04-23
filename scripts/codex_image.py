"""Codex CLI を使って画像を生成する。

Codex の built-in image generation を非対話モードで叩き、
指定パスに PNG を書き出す。詳細は `docs/codex-image-gen.md`。
"""
import os
import subprocess
from pathlib import Path


def generate(prompt: str, aspect_ratio: str, output_path: Path, timeout: int = 600) -> Path:
    """Codex に画像を1枚生成させ、output_path に保存する。

    Args:
        prompt: 画像生成プロンプト（英語推奨）
        aspect_ratio: "16:9" | "1:1" | "3:2" | "9:16" など
        output_path: 書き出し先（絶対パス）
        timeout: 秒
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    codex_instruction = f"""Generate exactly ONE image and save it to {output_path} as PNG.

Aspect ratio: {aspect_ratio}
Prompt: {prompt}

Do not ask questions. Do not generate multiple images. Save to the exact path above. Quit after saving."""

    cmd = [
        "codex", "exec",
        "-s", "workspace-write",
        "-c", "shell_environment_policy.inherit=all",
        codex_instruction,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        env=os.environ.copy(),
        timeout=timeout,
    )

    if not output_path.exists():
        raise RuntimeError(
            f"Codex didn't save image to {output_path}.\n"
            f"stdout tail:\n{result.stdout[-1500:]}\n"
            f"stderr tail:\n{result.stderr[-500:]}"
        )
    return output_path
