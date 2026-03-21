# Extraction Model Comparison: spaCy vs JobBERT vs MCF

**Date:** 2026-03-21

## What

Compared three skill extraction approaches across 20 real JDs from MyCareersFuture.gov.sg:
- **spaCy** (`en_core_web_sm` 12 MB) + ESCO entity ruler — current pipeline
- **JobBERT** (`jjzha/jobbert_knowledge_extraction` ~410 MB) — NER model fine-tuned on job postings
- **MCF platform skills** — pre-extracted by Singapore government portal (free metadata per job listing)

JDs covered 4 categories: AI engineer, data scientist, software engineer, strategy consultant (5 each).

## Why

- User concerned spaCy + ESCO may not generalize across industries
- JobBERT proposed as industry-agnostic alternative
- Needed data to decide whether the 410 MB model cost was justified

## How

### Scripts used

| Script | Purpose |
|---|---|
| `scripts/fetch_jds.py` | Fetch JDs from MyCareersFuture API. Saves `.txt` (raw JD) and `.mcf.txt` (platform-extracted skills) as separate files to avoid contaminating model comparison. |
| `scripts/compare_extraction.py` | Runs spaCy and JobBERT on each `.txt` file, outputs per-JD summary table + detailed `comparison.csv` with columns: `file, skill, spacy, jobbert, mcf`. |
| `scripts/extract_legitimate_jobbert.py` | Filters `comparison.csv` for jobbert=yes + spacy=no rows, removes noise (## tokens, fragments, generic words), saves legitimate skills to `tests/claude_analyse_rest_txt_before.csv`. |

### Reproduction steps

```bash
# 1. Fetch JDs (already done — files in tests/fixtures/jds/)
uv run python scripts/fetch_jds.py "AI engineer" "data scientist" "strategy consultant" "software engineer" --count 5 --out tests/fixtures/jds

# 2. Run comparison (requires jobbert download ~410 MB on first run)
uv run python scripts/compare_extraction.py tests/fixtures/jds

# 3. Extract legitimate jobbert-only skills
uv run python scripts/extract_legitimate_jobbert.py
```

## Results

### Summary statistics

- **1,150** jobbert-only extractions (jobbert=yes, spacy=no) across 20 JDs
- **~162** unique skills after noise filtering (86% of raw output was WordPiece fragments/noise)
- **0%** MCF validation — none of the jobbert-only skills were confirmed by MCF platform
- spaCy extracted 39–180 skills per JD; jobbert extracted 0–165; agreement (both=yes) was only 0–25 per JD

### Decision: drop JobBERT

- 86% noise rate (## tokens, single chars, truncated words from BERT's 512-token chunking)
- 0% MCF cross-validation
- 410 MB model for ~14% legitimate extraction rate
- Legitimate finds are better addressed by MCF dictionary + custom skill list + fixing spaCy pipeline

### 4 root causes of spaCy false negatives identified

| Root cause | Example | Fix |
|---|---|---|
| **Substring suppression** (biggest) | `"data governance"` dropped because `"data governance frameworks"` exists | Phase 9C: allow shorter phrases to survive if they appear independently |
| **Single-token rejection** | `"algorithms"`, `"encryption"` rejected (not in allowlist, not TOOLISH) | Phase 9D/F: MCF + custom dictionary catches these via entity ruler |
| **Noun chunk boundary** | `"model registry"`, `"agent orchestration"` — modern MLOps terms `en_core_web_sm` doesn't parse | Phase 9D/F: MCF + custom dictionary |
| **vague_outcome_nouns filter** | `"continuous deployment"` — `deployment` is in the vague list | Phase 9C: review vague_outcome_nouns entries |

### Additional spaCy noise issues (from API-fetched JDs)

| Issue | Example | Fix |
|---|---|---|
| HTML tags in extracted skills | `</li>`, `<br>`, `<strong>` | Phase 9A: strip HTML before spaCy |
| URLs extracted as skills | `https://www.nmg-consulting.com/...` | Phase 9A: regex strip |
| Company names extracted | `"nmg financial services consulting pte ltd"` | Phase 9B/C: stoplist + header parsing |
| Education terms extracted | `"bachelor's degree"`, `"phd"` | Phase 9B: add to domain_stoplist |
| CI/CD split into separate tokens | `"ci"` and `"cd"` instead of `"CI/CD"` | Phase 9A: spaCy tokenizer exceptions |

## Output files

| File | Contents |
|---|---|
| `tests/fixtures/jds/comparison.csv` | Full per-skill comparison (3,038 rows) |
| `tests/claude_analyse_rest_txt_before.csv` | Filtered jobbert-only legitimate skills (~162 unique) — baseline before Phase 9 fixes |
