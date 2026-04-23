"""Claude Code CLI を subprocess 経由で叩くヘルパー。

Claude Pro/Max 契約を流用してテキスト生成を行う。ANTHROPIC_API_KEY 不要。

- `--system-prompt` で既存の Claude Code システムプロンプトを完全に置き換える
- `--tools ""` でツール呼び出しを禁止（純粋な生成のみ）
- `--session-id` + `--resume` で**同じセッション**を複数ターン回せる
  ⚠️ `--no-session-persistence` は使わない（resume できなくなる）
- `--bare` は使わない（ANTHROPIC_API_KEY を要求してしまうため）
"""
import json as jsonlib
import re
import subprocess
import uuid


def call_text(
    system_prompt: str,
    user_prompt: str,
    model: str = "opus",
    timeout: int = 900,
    tools: str = "",
    allowed_dirs: list[str] | None = None,
) -> str:
    """Claude に1回プロンプトを投げて結果のテキストを返す（単発・セッション持続なし）。

    - tools: Claude に許可するツール（"" で禁止、"Read" で Read のみ、"default" で全部）
    - allowed_dirs: Read 時のアクセス許可ディレクトリ
    """
    extra: list[str] = []
    if allowed_dirs:
        extra.extend(["--add-dir", *allowed_dirs])
    if tools:
        extra.extend(["--permission-mode", "bypassPermissions"])
    cmd = [
        "claude", "-p", user_prompt,
        "--system-prompt", system_prompt,
        "--tools", tools,
        "--no-session-persistence",
        "--model", model,
        "--output-format", "text",
        *extra,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI failed (exit {result.returncode}):\n"
            f"stdout tail:\n{result.stdout[-1500:]}\n"
            f"stderr tail:\n{result.stderr[-1500:]}"
        )
    return result.stdout.strip()


def call_json(
    system_prompt: str,
    user_prompt: str,
    model: str = "opus",
    timeout: int = 600,
) -> dict:
    """単発で JSON を出させて dict でパース。"""
    text = call_text(system_prompt, user_prompt, model=model, timeout=timeout)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    text = text.strip()
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found:\n{text[:2000]}")
    depth = 0
    end = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text[start:], start=start):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise ValueError(f"unbalanced braces:\n{text[:2000]}")
    js = text[start:end]
    try:
        return jsonlib.loads(js)
    except jsonlib.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}\n\n--- extracted ---\n{js[:3000]}")


# ========================== Session-aware ==========================

def new_session_id() -> str:
    """セッション ID 発行。"""
    return str(uuid.uuid4())


def session_turn(
    session_id: str,
    user_prompt: str,
    system_prompt: str | None = None,
    resume: bool = False,
    model: str = "opus",
    timeout: int = 900,
    tools: str = "",
    allowed_dirs: list[str] | None = None,
) -> str:
    """指定セッションで1ターン回す。

    - 初回（resume=False）: `--session-id` で新規セッション起動 + `--system-prompt` を渡す
    - 2回目以降（resume=True）: `--resume` でセッション再開（system は引き継がれる）
    - tools: Claude に許可するツール（"" で禁止、"Read" で Read のみ、"default" で全部）
    - allowed_dirs: Read 時のアクセス許可ディレクトリ

    セッション永続化を使うので `--no-session-persistence` は**付けない**。
    """
    extra: list[str] = []
    if allowed_dirs:
        extra.extend(["--add-dir", *allowed_dirs])
    if tools:
        # Read を許可する場合、subprocess 実行でユーザー確認が出ないように bypass
        extra.extend(["--permission-mode", "bypassPermissions"])

    if resume:
        cmd = [
            "claude", "-p", user_prompt,
            "--resume", session_id,
            "--tools", tools,
            "--model", model,
            "--output-format", "text",
            *extra,
        ]
    else:
        if system_prompt is None:
            raise ValueError("initial turn requires system_prompt")
        cmd = [
            "claude", "-p", user_prompt,
            "--session-id", session_id,
            "--system-prompt", system_prompt,
            "--tools", tools,
            "--model", model,
            "--output-format", "text",
            *extra,
        ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI failed (exit {result.returncode}, session={session_id}, resume={resume}):\n"
            f"stdout tail:\n{result.stdout[-2000:]}\n"
            f"stderr tail:\n{result.stderr[-1500:]}"
        )
    return result.stdout.strip()


# ========================== Artifact extraction ==========================

def extract_block(text: str, tag: str) -> str | None:
    """`<!-- {tag}:BEGIN -->` と `<!-- {tag}:END -->` に挟まれた部分を返す。"""
    pattern = re.compile(
        rf"<!--\s*{re.escape(tag)}:BEGIN\s*-->(.*?)<!--\s*{re.escape(tag)}:END\s*-->",
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else None
