"""
Fetch job descriptions from MyCareersFuture.gov.sg public API and save as .txt files.

Usage:
    uv run python scripts/fetch_jds.py "data analyst" --count 10 --out tests/fixtures/jds
    uv run python scripts/fetch_jds.py "software engineer" --count 5
    uv run python scripts/fetch_jds.py "financial analyst" "marketing manager" --count 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

API_URL = "https://api.mycareersfuture.gov.sg/v2/jobs"
DEFAULT_OUT = Path("tests/fixtures/jds")
MCF_DICT_PATH = Path("config/mcf_skills.json")


def fetch_jobs(query: str, count: int) -> list[dict]:
    params = {"search": query, "limit": count, "sort": "new_posting_date", "order": "desc"}
    try:
        r = httpx.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  ERROR fetching '{query}': {e}", file=sys.stderr)
        return []
    return r.json().get("results", [])


def safe_filename(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")


def save_job(job: dict, out_dir: Path, index: int, query: str) -> Path:
    title = job.get("title", "untitled")
    company = job.get("postedCompany", {}).get("name", "unknown")
    description = job.get("description", "").strip()

    # MCF skills are pre-extracted by the platform — useful reference for comparison
    mcf_skills = [s.get("skill", "") for s in job.get("skills", []) if s.get("skill")]

    slug = safe_filename(f"{query}_{index:02d}_{title[:40]}")

    # Main file: raw description only — no MCF skills (would contaminate extraction comparison)
    jd_content = "\n".join([f"Title: {title}", f"Company: {company}", "", description])
    path = out_dir / f"{slug}.txt"
    path.write_text(jd_content, encoding="utf-8")

    # Sidecar file: MCF's own extracted skills — use as reference benchmark, not model input
    mcf_path = out_dir / f"{slug}.mcf.txt"
    mcf_path.write_text("\n".join(mcf_skills) if mcf_skills else "(none listed)", encoding="utf-8")

    return path


def _accumulate_mcf_skills(out_dir: Path) -> int:
    """Append any new MCF skills from .mcf.txt files to the shared dictionary."""
    existing: set[str] = set()
    if MCF_DICT_PATH.exists():
        existing = set(json.loads(MCF_DICT_PATH.read_text(encoding="utf-8")))

    for f in out_dir.glob("*.mcf.txt"):
        text = f.read_text(encoding="utf-8").strip()
        if text == "(none listed)":
            continue
        for line in text.splitlines():
            skill = line.strip()
            if skill:
                existing.add(skill)

    sorted_skills = sorted(existing, key=str.lower)
    MCF_DICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCF_DICT_PATH.write_text(
        json.dumps(sorted_skills, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(sorted_skills) - len(existing)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch JDs from MyCareersFuture")
    parser.add_argument("queries", nargs="+", help="Job search queries")
    parser.add_argument("--count", type=int, default=5, help="Jobs per query (default: 5)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    total = 0
    for query in args.queries:
        print(f"Fetching '{query}' ({args.count} jobs)...")
        jobs = fetch_jobs(query, args.count)
        for i, job in enumerate(jobs, 1):
            path = save_job(job, args.out, i, query)
            print(f"  [{i}/{len(jobs)}] {path.name}")
            total += 1

    # Auto-accumulate MCF skills into dictionary
    new_skills = _accumulate_mcf_skills(args.out)
    if new_skills:
        print(f"Added {new_skills} new skill(s) to {MCF_DICT_PATH}")

    print(f"\nDone — {total} file(s) saved to {args.out}/")


if __name__ == "__main__":
    main()
