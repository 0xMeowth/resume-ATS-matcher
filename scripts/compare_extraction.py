"""
Compare skill extraction between spaCy (current) and JobBERT (proposed).

For each .txt JD file in the input directory, runs both models and outputs:
  - Terminal: one-line summary table per JD, sorted by most JobBERT-only skills
  - CSV: full skill-level diff at <out_dir>/comparison.csv
  - MCF sidecar skills (if available) shown as a reference column in CSV

Usage:
    uv run python scripts/compare_extraction.py tests/fixtures/jds
    uv run python scripts/compare_extraction.py tests/fixtures/jds --out results/
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ── spaCy extractor (existing pipeline) ──────────────────────────────────────

def extract_spacy(text: str, parser) -> set[str]:
    result = parser.extract_skill_components(text)
    return {s.lower().strip() for s in result.get("combined_skills", [])}


# ── JobBERT extractor ─────────────────────────────────────────────────────────

def load_jobbert():
    from transformers import pipeline as hf_pipeline
    print("Loading jjzha/jobbert_knowledge_extraction (downloads on first run ~410 MB)...")
    # aggregation_strategy="none" gives raw B/I/O token labels which we merge manually
    return hf_pipeline(
        "token-classification",
        model="jjzha/jobbert_knowledge_extraction",
        aggregation_strategy="none",
    )


def _merge_bio(entities: list[dict]) -> list[str]:
    """Merge consecutive B/I tokens into skill phrases, handling WordPiece ## continuations."""
    skills, current = [], []
    for ent in entities:
        label = ent.get("entity", "O")
        word = ent.get("word", "")
        if label == "B":
            if current:
                skills.append(" ".join(current))
            current = [word]
        elif label == "I" and current:
            if word.startswith("##"):
                current[-1] += word[2:]
            else:
                current.append(word)
        else:
            if current:
                skills.append(" ".join(current))
            current = []
    if current:
        skills.append(" ".join(current))
    return skills


def extract_jobbert(text: str, pipe) -> set[str]:
    # BERT max is 512 tokens. 100 words × ~2.5 subword tokens/word ≈ 250 tokens — safely under limit.
    words = text.split()
    chunks = [" ".join(words[i:i + 100]) for i in range(0, len(words), 100)]
    skills: set[str] = set()
    for chunk in chunks:
        entities = pipe(chunk)
        for skill in _merge_bio(entities):
            skills.add(skill.lower().strip())
    return skills


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare spaCy vs JobBERT skill extraction")
    parser.add_argument("jd_dir", type=Path, help="Directory containing .txt JD files")
    parser.add_argument("--out", type=Path, default=None, help="Output dir for CSV (default: same as jd_dir)")
    args = parser.parse_args()

    jd_files = sorted(f for f in args.jd_dir.glob("*.txt") if not f.name.endswith(".mcf.txt"))
    if not jd_files:
        print(f"No .txt files found in {args.jd_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = args.out or args.jd_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "comparison.csv"

    # Load models once
    from ats_matcher.jd_parser import JDParser
    jd_parser = JDParser()
    jobbert_pipe = load_jobbert()
    print(f"\nProcessing {len(jd_files)} files...\n")

    rows: list[dict] = []
    summary: list[dict] = []

    for jd_file in jd_files:
        text = jd_file.read_text(encoding="utf-8")

        spacy_skills = extract_spacy(text, jd_parser)
        jobbert_skills = extract_jobbert(text, jobbert_pipe)

        mcf_file = jd_file.with_suffix(".mcf.txt")
        mcf_skills = (
            {s.lower().strip() for s in mcf_file.read_text(encoding="utf-8").split(",")}
            if mcf_file.exists() else set()
        )

        both        = spacy_skills & jobbert_skills
        spacy_only  = spacy_skills - jobbert_skills
        jobbert_only = jobbert_skills - spacy_skills

        summary.append({
            "file": jd_file.name,
            "spacy": len(spacy_skills),
            "jobbert": len(jobbert_skills),
            "both": len(both),
            "spacy_only": len(spacy_only),
            "jobbert_only": len(jobbert_only),
        })

        # One CSV row per unique skill across both models
        all_skills = spacy_skills | jobbert_skills
        for skill in sorted(all_skills):
            rows.append({
                "file": jd_file.name,
                "skill": skill,
                "spacy": "yes" if skill in spacy_skills else "no",
                "jobbert": "yes" if skill in jobbert_skills else "no",
                "mcf": "yes" if skill in mcf_skills else "no" if mcf_skills else "n/a",
            })

    # ── Terminal summary table ────────────────────────────────────────────────
    summary.sort(key=lambda r: r["jobbert_only"], reverse=True)
    col = 48
    print(f"{'File':<{col}} {'spaCy':>6} {'JobBERT':>8} {'Both':>6} {'spaCy-only':>11} {'JobBERT-only':>13}")
    print("-" * (col + 50))
    for r in summary:
        print(
            f"{r['file']:<{col}} {r['spacy']:>6} {r['jobbert']:>8} "
            f"{r['both']:>6} {r['spacy_only']:>11} {r['jobbert_only']:>13}"
        )

    # ── CSV output ────────────────────────────────────────────────────────────
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "skill", "spacy", "jobbert", "mcf"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDetailed CSV saved to: {csv_path}")


if __name__ == "__main__":
    main()
