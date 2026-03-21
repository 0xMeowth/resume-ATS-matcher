"""
Extract legitimate jobbert-only skills from comparison.csv.

Filters jobbert=yes + spacy=no rows, removes obvious noise
(##-prefixed, single chars, fragments), and saves results.

Usage:
    uv run python scripts/extract_legitimate_jobbert.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

CSV_PATH = Path("tests/fixtures/jds/comparison.csv")
OUT_PATH = Path("tests/claude_analyse_rest_txt_before.csv")

# Noise patterns — items matching any of these are filtered out
NOISE_PATTERNS = [
    re.compile(r"##"),              # WordPiece continuation tokens
    re.compile(r"^\W+$"),           # Pure punctuation
    re.compile(r"[<>]"),            # HTML tag remnants
    re.compile(r"\bp\s*>\s*>"),     # HTML fragments like "p > >"
    re.compile(r"[^a-zA-Z0-9\s/&\-+#.]"),  # Unusual chars (corruption signal)
]

# Generic/fragment single words that are never skills on their own
GENERIC_SINGLES = {
    "advanced", "agent", "analytic", "applied", "architect", "art", "audit",
    "authentic", "automation", "back", "based", "bay", "big", "bio", "chain",
    "child", "client", "cloud", "col", "commerce", "computing", "con",
    "conceptual", "consulting", "container", "core", "dense", "deployment",
    "design", "digital", "dock", "driven", "dynamics", "economics", "end",
    "engineering", "english", "error", "evaluation", "experiment", "face",
    "few", "filtering", "finance", "fine", "fraud", "front", "fun", "gene",
    "growth", "had", "hall", "hardware", "healthcare", "heart", "high", "how",
    "imaging", "implementation", "infrastructure", "insurance", "integration",
    "japanese", "lang", "lea", "learn", "level", "life", "local", "logistics",
    "map", "maritime", "master", "mathematics", "measurement", "met", "meta",
    "micro", "model", "modern", "mon", "multi", "new", "next", "non",
    "notebook", "open", "orient", "out", "parent", "payments", "performance",
    "physics", "pine", "port", "power", "pro", "programming", "prototypes",
    "que", "radio", "real", "reasoning", "red", "regulations", "responsible",
    "robot", "robotic", "script", "security", "semi", "service", "sing",
    "singapore", "single", "snow", "software", "sol", "source", "spa",
    "sparse", "stake", "statistical", "statistics", "step", "suite", "system",
    "table", "ten", "testing", "thread", "time", "token", "tools", "trans",
    "transformers", "tuning", "type", "unit", "unix", "version", "visual",
    "whole", "wire", "word", "clinical", "ang", "aug", "gen",
    # Education terms (will be excluded in Phase 9B)
    "bachelor", "master", "phd", "degree", "diploma", "education",
}

# Known short abbreviations that ARE legitimate skills
SHORT_ALLOWLIST = {"api", "sql", "aws", "gcp", "ai", "ml", "ci", "cd", "c++", "c#", "r"}


def is_noise(skill: str) -> bool:
    s = skill.strip().lower()
    if len(s) <= 2 and s not in SHORT_ALLOWLIST:
        return True
    for pat in NOISE_PATTERNS:
        if pat.search(skill.strip()):
            return True
    words = s.split()
    # Single-word fragments / generic terms
    if len(words) == 1 and s not in SHORT_ALLOWLIST and (len(s) <= 4 or s in GENERIC_SINGLES):
        return True
    # Phrases starting/ending with fragments
    if words[0] in {"s", "s ,", "d", "d ."} or words[-1] in {")", "(", "/", ","}:
        return True
    # Corrupted multi-word: first word is a 1-2 char fragment
    if len(words[0]) <= 2 and words[0] not in {"ai", "ml", "or", "of", "in", "an", "&", "/"}:
        return True
    # Trailing preposition/conjunction = incomplete phrase
    if words[-1] in {"and", "or", "of", "in", "for", "to", "the", "a", "an", ")", "(", "/", ",", "&"}:
        return True
    # Leading fragments from chunk boundaries ("based X", "driven X", "assisted X")
    if words[0] in {"based", "driven", "assisted"}:
        return True
    # Obvious truncation: word ends mid-syllable (heuristic: ends with consonant cluster unlikely to be a real word ending)
    CORRUPTION_MARKERS = {"stgies", "compo", "optimi", "ology", "engineeringy", "identificationization", "avia"}
    if any(m in s for m in CORRUPTION_MARKERS):
        return True
    # Phrase starts with "of -" or similar dangling
    if s.startswith("of ") or s.startswith("cd ") or s.startswith("s "):
        return True
    return False


def main() -> None:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found")
        return

    # Read all jobbert-only rows
    jobbert_only: list[dict] = []
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["jobbert"] == "yes" and row["spacy"] == "no":
                jobbert_only.append(row)

    print(f"Total jobbert-only rows: {len(jobbert_only)}")

    # Classify as legitimate or noise
    legitimate = []
    noise_count = 0
    for row in jobbert_only:
        if is_noise(row["skill"]):
            noise_count += 1
        else:
            legitimate.append(row)

    print(f"Noise filtered out: {noise_count}")
    print(f"Legitimate skills: {len(legitimate)}")

    # Deduplicate skills across files
    unique_skills = sorted(set(row["skill"] for row in legitimate))
    print(f"Unique legitimate skills: {len(unique_skills)}")

    # Write per-file detail CSV
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "skill", "mcf"])
        writer.writeheader()
        for row in sorted(legitimate, key=lambda r: (r["file"], r["skill"])):
            writer.writerow({"file": row["file"], "skill": row["skill"], "mcf": row["mcf"]})

    # Append summary section: deduplicated skill list
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write("\n# Deduplicated legitimate skills (jobbert found, spaCy missed)\n")
        for skill in unique_skills:
            f.write(f"{skill}\n")

    # Also print summary to terminal
    print(f"\nSaved to: {OUT_PATH}")
    print(f"\n--- Deduplicated legitimate skills ({len(unique_skills)}) ---")
    for skill in unique_skills:
        print(f"  {skill}")


if __name__ == "__main__":
    main()
