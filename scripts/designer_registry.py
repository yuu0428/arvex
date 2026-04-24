"""デザイナーペルソナの registry。

scripts/designers/<name>/SKILL.md を全部ロードして Designer オブジェクトで返す。
moodboard は <name>/moodboard/*.png として格納される（collect_moodboards.py が埋める）。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DESIGNERS_DIR = Path(__file__).resolve().parent / "designers"


@dataclass
class Designer:
    name: str  # slug
    dir: Path
    display_name: str
    description: str
    signature_fonts: list[str]
    palette_rules: str
    motion_profile: str
    persona_markdown: str  # SKILL.md の frontmatter 以降
    favorites_path: Path = field(default=None)  # favorites.json
    moodboard_dir: Path = field(default=None)

    def moodboard_paths(self) -> list[Path]:
        if not self.moodboard_dir or not self.moodboard_dir.exists():
            return []
        return sorted(self.moodboard_dir.glob("*.png")) + sorted(self.moodboard_dir.glob("*.jpg"))


def _parse_skill_md(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not m:
        return {}, content
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, m.group(2).strip()


def load_designers() -> list[Designer]:
    if not _DESIGNERS_DIR.exists():
        return []
    designers: list[Designer] = []
    for sub in sorted(_DESIGNERS_DIR.iterdir()):
        skill_md = sub / "SKILL.md"
        if not sub.is_dir() or not skill_md.exists():
            continue
        fm, body = _parse_skill_md(skill_md)
        designers.append(
            Designer(
                name=fm.get("name") or sub.name,
                dir=sub,
                display_name=fm.get("display_name") or sub.name,
                description=fm.get("description") or "",
                signature_fonts=fm.get("signature_fonts") or [],
                palette_rules=fm.get("palette_rules") or "",
                motion_profile=fm.get("motion_profile") or "",
                persona_markdown=body,
                favorites_path=sub / "favorites.json",
                moodboard_dir=sub / "moodboard",
            )
        )
    return designers


def get_designer(name: str) -> Designer | None:
    for d in load_designers():
        if d.name == name:
            return d
    return None


if __name__ == "__main__":
    for d in load_designers():
        print(f"{d.name:22} — {d.display_name}")
        print(f"  {d.description[:90]}")
        print(f"  fonts: {d.signature_fonts}")
        print(f"  moodboard: {len(d.moodboard_paths())} images")
        print()
