"""Check that every relative markdown link and backticked input path in the workspace resolves.

Run from the repo root: `python _tools/check_links.py`. Exit code 1 on any broken link.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", ".local", ".claude", "node_modules", "__pycache__", ".pytest_cache"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
INPUT_PATH = re.compile(r"`(\.\./[^`\s]+)`")


def iter_md(root: Path):
    for p in root.rglob("*.md"):
        if not any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            yield p


def main() -> int:
    broken: list[str] = []
    pending: list[str] = []
    for md in iter_md(ROOT):
        text = md.read_text(encoding="utf-8")
        targets = LINK.findall(text)
        if md.name == "CONTEXT.md":
            targets += INPUT_PATH.findall(text)
        for t in targets:
            if t.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = t.split("#", 1)[0].split(":", 1)[0]
            if not path or "{" in path:
                continue
            if (md.parent / path).exists():
                continue
            target = (md.parent / path).resolve()
            # an input from a stage that has not run yet is status, not a broken link
            if "output" in target.parts and target.parent.is_dir():
                pending.append(f"{md.relative_to(ROOT)} -> {t}")
            else:
                broken.append(f"{md.relative_to(ROOT)} -> {t}")
    for p in pending:
        print("pending (stage not run yet):", p)
    for b in broken:
        print("broken:", b)
    print(f"{'fail' if broken else 'pass'}: {len(broken)} broken link(s), {len(pending)} pending stage output(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
