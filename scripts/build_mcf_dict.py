"""Build a deduplicated MCF skill dictionary from .mcf.txt sidecar files.

Reads all *.mcf.txt files from specified directories, deduplicates,
and writes to config/mcf_skills.json.

Usage:
    uv run python scripts/build_mcf_dict.py
    uv run python scripts/build_mcf_dict.py --dirs data/mcf_jds tests/fixtures/jds
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_DIRS = [Path("data/mcf_jds"), Path("tests/fixtures/jds")]
OUT_PATH = Path("config/mcf_skills.json")


def collect_mcf_skills(dirs: list[Path]) -> set[str]:
    skills: set[str] = set()
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.mcf.txt")):
            text = f.read_text(encoding="utf-8").strip()
            if text == "(none listed)":
                continue
            for line in text.splitlines():
                skill = line.strip()
                if skill:
                    skills.add(skill)
    return skills


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MCF skill dictionary")
    parser.add_argument(
        "--dirs", nargs="*", type=Path, default=DEFAULT_DIRS,
        help="Directories containing .mcf.txt files",
    )
    args = parser.parse_args()

    skills = collect_mcf_skills(args.dirs)
    sorted_skills = sorted(skills, key=str.lower)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(sorted_skills, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(sorted_skills)} unique MCF skills to {OUT_PATH}")


if __name__ == "__main__":
    main()
