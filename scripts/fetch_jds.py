"""
Fetch job descriptions and save as .txt files.

Sources: MCF (MyCareersFuture), Greenhouse ATS, Lever ATS.

Usage:
    # MCF — single keyword
    uv run python scripts/fetch_jds.py "data analyst" --count 10

    # MCF — multiple keywords
    uv run python scripts/fetch_jds.py "software engineer" "ai engineer" --count 5

    # MCF — batch mode (reads keyword|count lines from file)
    uv run python scripts/fetch_jds.py --batch scripts/mcf_keywords.txt

    # Greenhouse (public API, no auth)
    uv run python scripts/fetch_jds.py --source greenhouse --companies stripe coinbase airbnb --count 10

    # Lever (public API, no auth)
    uv run python scripts/fetch_jds.py --source lever --companies binance --count 10

Output structure:
    tests/fixtures/jds/
      mcf/<keyword_slug>/01_<title>.txt + .mcf.txt
      greenhouse/<company>/01_<title>.txt
      lever/<company>/01_<title>.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import html

import httpx
from bs4 import BeautifulSoup

API_URL = "https://api.mycareersfuture.gov.sg/v2/jobs"
GREENHOUSE_API = "https://api.greenhouse.io/v1/boards/{company}/jobs"
LEVER_API = "https://api.lever.co/v0/postings/{company}"
DEFAULT_OUT = Path("tests/fixtures/jds")
MCF_DICT_PATH = Path("config/mcf_skills.json")
MCF_PAGE_SIZE = 100  # MCF API caps at 100 per request
MCF_SLEEP = 1.5  # seconds between API requests


def fetch_jobs_paginated(query: str, count: int) -> list[dict]:
    """Fetch MCF jobs with offset-based pagination (max 100 per page)."""
    all_jobs: list[dict] = []
    offset = 0
    while len(all_jobs) < count:
        page_limit = min(MCF_PAGE_SIZE, count - len(all_jobs))
        params = {
            "search": query,
            "limit": page_limit,
            "offset": offset,
            "sort": "new_posting_date",
            "order": "desc",
        }
        try:
            r = httpx.get(API_URL, params=params, timeout=15)
            r.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  ERROR fetching '{query}' (offset={offset}): {e}", file=sys.stderr)
            break
        data = r.json()
        results = data.get("results", [])
        total_available = data.get("total", 0)
        all_jobs.extend(results)
        offset += len(results)
        if not results or offset >= total_available:
            break
        if len(all_jobs) < count:
            time.sleep(MCF_SLEEP)
    return all_jobs[:count]


def safe_filename(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")


def save_job(job: dict, out_dir: Path, index: int) -> Path:
    title = job.get("title", "untitled")
    company = job.get("postedCompany", {}).get("name", "unknown")
    description = job.get("description", "").strip()

    mcf_skills = [s.get("skill", "") for s in job.get("skills", []) if s.get("skill")]

    slug = safe_filename(f"{index:02d}_{title[:40]}")

    jd_content = "\n".join([f"Title: {title}", f"Company: {company}", "", description])
    path = out_dir / f"{slug}.txt"
    path.write_text(jd_content, encoding="utf-8")

    mcf_path = out_dir / f"{slug}.mcf.txt"
    mcf_path.write_text("\n".join(mcf_skills) if mcf_skills else "(none listed)", encoding="utf-8")

    return path


def _accumulate_mcf_skills(out_dir: Path) -> int:
    """Append any new MCF skills from .mcf.txt files to the shared dictionary."""
    existing: set[str] = set()
    if MCF_DICT_PATH.exists():
        existing = set(json.loads(MCF_DICT_PATH.read_text(encoding="utf-8")))

    before = len(existing)
    for f in out_dir.rglob("*.mcf.txt"):
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
    return len(sorted_skills) - before


def _existing_jd_count(folder: Path) -> int:
    """Count existing .txt files (excluding .mcf.txt) in a folder."""
    if not folder.exists():
        return 0
    return len([f for f in folder.glob("*.txt") if not f.name.endswith(".mcf.txt")])


def _html_to_text(raw: str) -> str:
    """Decode HTML entities and strip tags to plain text."""
    decoded = html.unescape(raw)
    return BeautifulSoup(decoded, "html.parser").get_text("\n", strip=True)


def fetch_greenhouse(company: str, count: int) -> list[dict]:
    """Fetch jobs from Greenhouse public Job Board API."""
    url = GREENHOUSE_API.format(company=company)
    try:
        r = httpx.get(url, params={"content": "true"}, timeout=15)
        r.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  ERROR fetching Greenhouse '{company}': {e}", file=sys.stderr)
        return []
    jobs = r.json().get("jobs", [])
    return jobs[:count]


def save_greenhouse_job(job: dict, out_dir: Path, index: int, company: str) -> Path:
    """Save a Greenhouse job as a .txt fixture."""
    title = job.get("title", "untitled")
    content_html = job.get("content", "")
    description = _html_to_text(content_html) if content_html else ""

    slug = safe_filename(f"{index:02d}_{title[:40]}")
    jd_content = "\n".join([f"Title: {title}", f"Company: {company}", "", description])
    path = out_dir / f"{slug}.txt"
    path.write_text(jd_content, encoding="utf-8")
    return path


def fetch_lever(company: str, count: int) -> list[dict]:
    """Fetch jobs from Lever public Postings API."""
    url = LEVER_API.format(company=company)
    try:
        r = httpx.get(url, params={"mode": "json", "limit": count}, timeout=15)
        r.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  ERROR fetching Lever '{company}': {e}", file=sys.stderr)
        return []
    return r.json()[:count] if isinstance(r.json(), list) else []


def save_lever_job(job: dict, out_dir: Path, index: int, company: str) -> Path:
    """Save a Lever job as a .txt fixture."""
    title = job.get("text", "untitled")
    desc_html = job.get("descriptionPlain") or job.get("description", "")
    lists_html = "\n".join(
        item.get("content", "") for item in job.get("lists", [])
    )
    additional = job.get("additionalPlain") or job.get("additional", "")

    parts = [desc_html]
    if lists_html:
        parts.append(_html_to_text(lists_html))
    if additional:
        parts.append(additional if isinstance(additional, str) else "")
    description = "\n\n".join(p for p in parts if p.strip())

    slug = safe_filename(f"{index:02d}_{title[:40]}")
    jd_content = "\n".join([f"Title: {title}", f"Company: {company}", "", description])
    path = out_dir / f"{slug}.txt"
    path.write_text(jd_content, encoding="utf-8")
    return path


def _parse_batch_file(path: Path) -> list[tuple[str, int]]:
    """Parse a batch file with keyword|count lines."""
    entries: list[tuple[str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        keyword = parts[0].strip()
        count = int(parts[1].strip()) if len(parts) > 1 else 200
        entries.append((keyword, count))
    return entries


def _run_mcf(queries: list[tuple[str, int]], out_dir: Path) -> int:
    """Fetch MCF jobs for each query, save to mcf/<keyword_slug>/ subfolders."""
    total = 0
    for query, count in queries:
        keyword_slug = safe_filename(query)
        keyword_dir = out_dir / "mcf" / keyword_slug
        existing = _existing_jd_count(keyword_dir)
        if existing >= count:
            print(f"Skipping MCF '{query}' — already have {existing} files (>= {count})")
            continue

        keyword_dir.mkdir(parents=True, exist_ok=True)
        # Start indexing after existing files
        start_index = existing + 1

        print(f"Fetching MCF '{query}' ({count} jobs, have {existing})...")
        jobs = fetch_jobs_paginated(query, count - existing)
        for i, job in enumerate(jobs, start_index):
            path = save_job(job, keyword_dir, i)
            print(f"  [{i}/{existing + len(jobs)}] {path.name}")
            total += 1

        if queries.index((query, count)) < len(queries) - 1 and jobs:
            time.sleep(MCF_SLEEP)

    # Auto-accumulate MCF skills into dictionary
    new_skills = _accumulate_mcf_skills(out_dir)
    if new_skills > 0:
        skill_count = len(json.loads(MCF_DICT_PATH.read_text(encoding="utf-8")))
        print(f"Added {new_skills} new skill(s) to {MCF_DICT_PATH} (total: {skill_count})")
    return total


def _run_greenhouse(companies: list[str], count: int, out_dir: Path) -> int:
    total = 0
    for company in companies:
        company_dir = out_dir / "greenhouse" / safe_filename(company)
        company_dir.mkdir(parents=True, exist_ok=True)
        print(f"Fetching Greenhouse '{company}' ({count} jobs)...")
        jobs = fetch_greenhouse(company, count)
        for i, job in enumerate(jobs, 1):
            path = save_greenhouse_job(job, company_dir, i, company)
            print(f"  [{i}/{len(jobs)}] {path.name}")
            total += 1
    return total


def _run_lever(companies: list[str], count: int, out_dir: Path) -> int:
    total = 0
    for company in companies:
        company_dir = out_dir / "lever" / safe_filename(company)
        company_dir.mkdir(parents=True, exist_ok=True)
        print(f"Fetching Lever '{company}' ({count} jobs)...")
        jobs = fetch_lever(company, count)
        for i, job in enumerate(jobs, 1):
            path = save_lever_job(job, company_dir, i, company)
            print(f"  [{i}/{len(jobs)}] {path.name}")
            total += 1
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch JDs from MCF / Greenhouse / Lever")
    parser.add_argument("queries", nargs="*", help="Job search queries (MCF mode)")
    parser.add_argument("--source", choices=["mcf", "greenhouse", "lever"], default="mcf",
                        help="Source: mcf (default), greenhouse, lever")
    parser.add_argument("--companies", nargs="+", help="Company slugs (greenhouse/lever mode)")
    parser.add_argument("--count", type=int, default=5, help="Jobs per query/company (default: 5)")
    parser.add_argument("--batch", type=Path, help="Batch file with keyword|count lines (MCF only)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    args = parser.parse_args()

    if args.batch:
        if args.source != "mcf":
            parser.error("--batch is only supported for MCF mode")
        queries = _parse_batch_file(args.batch)
        total = _run_mcf(queries, args.out)
    elif args.source == "mcf":
        if not args.queries:
            parser.error("MCF mode requires at least one search query (or --batch)")
        queries = [(q, args.count) for q in args.queries]
        total = _run_mcf(queries, args.out)
    elif args.source == "greenhouse":
        if not args.companies:
            parser.error("greenhouse mode requires --companies")
        total = _run_greenhouse(args.companies, args.count, args.out)
    elif args.source == "lever":
        if not args.companies:
            parser.error("lever mode requires --companies")
        total = _run_lever(args.companies, args.count, args.out)
    else:
        total = 0

    print(f"\nDone — {total} file(s) saved to {args.out}/")


if __name__ == "__main__":
    main()
