"""
strip_solutions.py — turn the MASTER repo into the STUDENT repo.

You keep ONE source of truth (this repo, with solutions). Solutions are wrapped
in markers. This script mirrors the repo to an output folder, replacing each
marked block with a stub so students implement it themselves. Edit once here,
regenerate the student repo, push.

Marker convention (Python files AND notebook cells):

    def sma(prices, window):
        \"\"\"docstring stays\"\"\"
        # ---8<--- solution
        out = ...real code...
        return out
        # ---8<--- end

becomes:

    def sma(prices, window):
        \"\"\"docstring stays\"\"\"
        raise NotImplementedError  # YOUR CODE HERE

Usage:
    uv run python scripts/strip_solutions.py . ../efg-algo-internship-student
"""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path

BEGIN = "# ---8<--- solution"
END = "# ---8<--- end"
STUB = "raise NotImplementedError  # YOUR CODE HERE"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".ipynb_checkpoints", "models"}


def strip_text(text: str) -> str:
    """Replace each marked block with an indented stub."""
    lines = text.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        if BEGIN in lines[i]:
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
            out.append(f"{indent}{STUB}\n")
            while i < len(lines) and END not in lines[i]:
                i += 1
            i += 1  # skip the END line
        else:
            out.append(lines[i]); i += 1
    return "".join(out)


def strip_notebook(text: str) -> str:
    """Same, but per code cell inside a .ipynb."""
    nb = json.loads(text)
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            src = "".join(cell.get("source", []))
            if BEGIN in src:
                cell["source"] = strip_text(src).splitlines(keepends=True)
                cell["outputs"] = []
                cell["execution_count"] = None
    return json.dumps(nb, indent=1)


def main(src: str, dst: str) -> None:
    src, dst = Path(src).resolve(), Path(dst).resolve()
    if dst.exists():
        shutil.rmtree(dst)
    for p in src.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(src)
        target = dst / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".py":
            target.write_text(strip_text(p.read_text()))
        elif p.suffix == ".ipynb":
            target.write_text(strip_notebook(p.read_text()))
        else:
            shutil.copy2(p, target)
    print(f"student repo generated at {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python scripts/strip_solutions.py SRC DST"); sys.exit(1)
    main(sys.argv[1], sys.argv[2])
