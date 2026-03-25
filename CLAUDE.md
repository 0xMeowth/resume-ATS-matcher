# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Setup:**
```bash
uv sync
uv pip install -e .          # installs ats_matcher as editable package (required for backend)
```

**Run (Streamlit — Phase 1):**
```bash
uv run streamlit run app.py
```

**Run (FastAPI backend — Phase 2+):**
```bash
uv run uvicorn backend.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

**Run (React frontend — Phase 2+):**
```bash
cd frontend && npm install && npm run dev
# UI at http://localhost:5173
```

**Database migration (Phase 3+):**
```bash
uv run python db/migrate.py
# ATS_DB_PATH=/custom/path.db uv run python db/migrate.py
```

**Run (Docker Compose — both services):**
```bash
docker compose up --build
# Frontend at http://localhost  (port 80)
# Backend at http://localhost:8000
# First build downloads spaCy + HuggingFace models (~1-2 GB); subsequent runs use the model_cache volume
```

**Test:**
```bash
uv run pytest                                                        # all tests
uv run pytest tests/test_matching_engine.py                          # one file
uv run pytest tests/test_matching_engine.py::test_exact_match        # one test
uv run pytest -k "skill and missing"                                 # by keyword
uv run pytest -x                                                     # stop on first failure
```

**Lint/Format:**
```bash
uv run ruff check .          # lint
uv run ruff format .         # format
```

**Smoke checks (always valid):**
```bash
uv run python -c "import ats_matcher"
uv run python -m compileall src app.py main.py
```

## Architecture

The app is a human-in-the-loop resume tailoring tool. Users upload a `.docx` resume, provide a job description (URL or paste), and receive keyword coverage analysis plus AI-assisted rewrite suggestions.

**5-step pipeline:**

1. **Parse resume** — `resume_parser.py` reads `.docx` into `ResumeData` (sections → roles → bullets with stable IDs)
2. **Parse JD** — `jd_parser.py` extracts skill terms via spaCy (`en_core_web_sm`) + an ESCO entity ruler; `config/skill_extraction.yaml` controls stopwords, allowlists, and light-head stripping
3. **Rank & embed** — `phrase_ranker.py` selects top-K skills (MMR, TF-IDF, or Hybrid); `embedding_engine.py` lazily loads `all-MiniLM-L6-v2` and encodes skills + bullets
4. **Match** — `matching_engine.py` classifies each skill as `exact`, `semantic_strong`, `semantic_weak`, or `missing` against resume bullets; `rewrite_engine.py` generates hints for non-exact matches
5. **Export** — `exporter.py` applies user-accepted edits back to the original `.docx`

**Key boundaries:**
- All business logic lives in `src/ats_matcher/`; `app.py` is pure Streamlit orchestration
- `models.py` owns all shared dataclasses (`Bullet`, `Role`, `Section`, `ResumeData`, `PhraseMatch`, `RewriteSuggestion`)
- Session state keys in `app.py` are stable and explicit — do not rename without updating all references

## Code Conventions

- Absolute imports: `from ats_matcher.models import ResumeData`
- Type-annotate all public functions; use `from __future__ import annotations`
- Use `dataclass` for domain objects; avoid `Any`
- PEP 8, 4-space indent, 88–100 char line length
- Prefer early returns for guard conditions
- Keep business logic out of `app.py` — add it to the appropriate `src/ats_matcher/` module

## Change Scope

- Prefer minimal diffs; avoid broad refactors alongside feature/bug fixes
- Do not introduce new heavy dependencies without clear need
- Preserve backward-compatible interfaces for existing call sites
- After any change, run relevant tests then verify `uv run streamlit run app.py` still launches

## Current Status

Before starting any work, read the **Progress Tracker** table at the top of `ROADMAP.md`. It shows which stages are `done`, `in-progress`, or `pending`. After completing a stage, update the table before moving on.

## Working in Stages

Any task estimated at more than ~30 minutes of work must be decomposed into named stages before starting. Rules for all future Claude instances working in this repo:

- **Decompose first** — before writing code for a large task, list the stages and get confirmation.
- **One stage at a time** — never attempt an entire phase in one shot.
- **After each stage:**
  1. Run the stage's verification command (listed in ROADMAP.md or defined ad-hoc).
  2. Write a one-line summary of what was done and what the next stage is.
  3. Commit the stage with a focused, descriptive message.
- **Track progress** — use `TaskCreate`/`TaskUpdate` within a session to track stage status.
- **Commit after each stage** — small, focused commits ensure progress is never lost to a session cutoff.
- **Never batch stages** — if a stage fails its verification, stop and fix before moving to the next stage.
