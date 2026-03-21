# Architecture

A human-in-the-loop resume tailoring tool. The user uploads a resume, provides a job description, reviews keyword coverage, edits AI-generated rewrite suggestions, and exports a tailored `.docx`.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite), served by Nginx in Docker |
| Backend | FastAPI (Python), Uvicorn |
| NLP / Embeddings | spaCy `en_core_web_sm`, `BAAI/bge-small-en-v1.5` (sentence-transformers) |
| Optional reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (opt-in via `USE_CROSS_ENCODER=1`) |
| Local LLM (rewrites) | Ollama (`llama3` or compatible), called over HTTP |
| Database | SQLite + `sqlite-vec` extension |
| Packaging | `uv`, editable install of `ats_matcher` package |

---

## How It Works (Plain English)

### Step 1: Extracting skills from a job description

- The raw JD text is **cleaned up first** — we strip out HTML tags, URLs, and email addresses so the NLP model doesn't get confused by non-text noise.
- The cleaned text is fed into **spaCy**, a lightweight NLP library (~12 MB). spaCy does two things:
  - **Tokenization** — splits the text into words and phrases
  - **Noun chunk detection** — identifies multi-word phrases like "data governance" or "machine learning pipelines" using grammar rules (which words are nouns, adjectives, etc.)
- On top of spaCy, we run **three skill dictionaries** as pattern matchers. If a phrase in the JD matches a known skill in any dictionary, it gets flagged:
  - **ESCO** (~6,000 skills) — the European Skills/Competences taxonomy, an official EU standard
  - **MCF** (~780 skills) — scraped from Singapore's MyCareersFuture job portal, where the government pre-tags each listing with skills
  - **Custom** (~22 skills) — manually curated terms we found through testing (e.g. "model registry", "agent orchestration")
- Candidates go through **filtering** — we remove generic words ("experience", "team", "bachelor's degree"), company names, and anything too short or vague.
- Finally, **deduplication** collapses near-duplicates. "strategy frameworks" and "strategy framework" become one entry. If "data governance" only appears inside "data governance frameworks", we keep the longer one. But if "data governance" also appears on its own somewhere in the JD, we keep both.

### Step 2: Matching skills against your resume

- Each extracted skill term needs to be checked against every bullet point in your resume. We do this in two passes:
  - **Exact match** — simple substring search. If the JD says "Python" and your bullet contains "Python", that's an exact match. Fast and reliable.
  - **Semantic match** — for skills that don't appear word-for-word in your resume. We convert both the skill term and each resume bullet into **embeddings** (numerical vectors that capture meaning). We use a model called `bge-small-en-v1.5` (~133 MB) for this. Then we measure **cosine similarity** — how close two vectors point in the same direction. Think of it like: "Python scripting" and "wrote automation scripts in Python" mean similar things, even though the words are different.
- Based on the similarity score, each skill gets a label:
  - **exact** — the skill appears word-for-word in your resume
  - **semantic_strong** (score >= 0.7) — your resume clearly covers this skill, just with different wording
  - **semantic_weak** (score >= 0.55) — your resume partially covers this, but the connection is loose
  - **missing** (score < 0.55) — your resume doesn't address this skill at all
- Optionally, a **cross-encoder** (~85 MB) can re-score the top candidates. Unlike the embedding model (which encodes skill and bullet separately), the cross-encoder reads them together as one input — slower but more accurate for borderline cases.

---

## Request flow

```
User (browser)
    │
    │  Step 1 — POST /api/resume
    ▼
[ResumeParser]  ←  .docx or .pdf bytes
    │  Parses into ResumeData (sections → roles → bullets, each with a stable bullet_id)
    │  Stored in-memory as ResumeEntry (keyed by resume_id UUID)
    ▼
    │  Step 2 — POST /api/jd/analyze
    ▼
[JDParser]  ←  raw JD text or URL
    │  spaCy NER + ESCO entity ruler → noun chunk candidates
    │  Filtered by skill_extraction.yaml (stopwords, allowlists, light_head stripping)
    │  Output: combined_skills (deduplicated candidate list)
    │
[EmbeddingEngine]  (BAAI/bge-small-en-v1.5, lazy-loaded)
    │  Encodes skill candidates + full JD doc with BGE query prefix
    │  Encodes resume bullets without prefix (passage side)
    │
[PhraseRanker]  (mmr | tfidf | hybrid, default: mmr)
    │  Selects top-K skill terms (default 120) from candidates
    │  MMR balances relevance-to-JD vs. diversity among selected terms
    │
[MatchingEngine]
    │  For each selected skill term:
    │    1. Exact match — normalized substring check against all bullets
    │    2. Semantic match — cosine similarity of skill vs. bullet embeddings
    │       - ≥ 0.7  → semantic_strong
    │       - ≥ 0.55 → semantic_weak
    │       - below  → missing
    │    3. Optional cross-encoder rerank of top-K candidates (USE_CROSS_ENCODER=1)
    │       sigmoid-normalised score replaces cosine before threshold comparison
    │  Output: List[PhraseMatch] with match_type + evidence_bullet_id
    │
[RewriteEngine]  (async, Ollama)
    │  For each non-exact match with a weak/missing label, calls Ollama to generate
    │  a suggested bullet rewrite. Falls back to stub if Ollama is unavailable.
    │  Output: List[RewriteSuggestion]
    │
    │  Analysis stored in-memory as AnalysisEntry (keyed by analysis_id UUID)
    ▼
    │  Step 3 — Coverage tab (frontend)
    │  User reviews skill_matches table; clicks +/- to label each row
    │    → POST /api/feedback  →  log_feedback()  →  skill_feedback table
    │
    │  Step 4 — Review tab (frontend)
    │  User accepts/edits rewrite suggestions per bullet
    │
    │  Step 5 — POST /api/export
    ▼
[Exporter]
    │  Applies accepted_changes (bullet_id → new_text) back to original .docx bytes
    │
[log_export()]  (db/writer.py)
    │  Writes atomically to: jobs, resumes, cv_pairs, cv_pair_embeddings
    ▼
Returns tailored .docx as binary download
```

---

## In-memory state (per server process)

State is held in `app.state` — not persisted across restarts.

| Key | Type | Lifetime |
|---|---|---|
| `resume_store` | `dict[str, ResumeEntry]` | Until process restart |
| `analysis_store` | `dict[str, AnalysisEntry]` | Until process restart |
| `jd_parser` | `JDParser` singleton | Process lifetime |
| `embedding_engine` | `EmbeddingEngine` singleton (lazy model load) | Process lifetime |
| `cross_encoder` | `CrossEncoder` or `None` | Process lifetime |

---

## Key source files

| File | Role |
|---|---|
| `backend/main.py` | FastAPI app, lifespan (startup: DB migrate, singleton init) |
| `backend/routers.py` | All API endpoints + Pydantic schemas |
| `backend/stores.py` | `ResumeEntry`, `AnalysisEntry` dataclasses; `new_id()` |
| `src/ats_matcher/resume_parser.py` | `.docx`/`.pdf` → `ResumeData` |
| `src/ats_matcher/jd_parser.py` | JD text → skill candidates |
| `src/ats_matcher/phrase_ranker.py` | MMR / TF-IDF phrase selection |
| `src/ats_matcher/embedding_engine.py` | `bge-small-en-v1.5` wrapper, asymmetric prefix |
| `src/ats_matcher/matching_engine.py` | Exact + semantic match classification |
| `src/ats_matcher/rewrite_engine.py` | Ollama async rewrite suggestions |
| `src/ats_matcher/exporter.py` | Apply edits back to `.docx` |
| `src/ats_matcher/models.py` | Shared dataclasses (`ResumeData`, `PhraseMatch`, etc.) |
| `config/skill_extraction.yaml` | Stopwords, allowlists, light-head terms for JD parsing |
| `db/migrate.py` | Schema creation (idempotent) |
| `db/writer.py` | `log_export()`, `log_feedback()` |
| `db/connection.py` | sqlite-vec extension loader, connection factory |
| `frontend/src/App.jsx` | 5-step wizard, all shared state lifted here |

---

## Frontend wizard

5 steps, all state lifted into `App.jsx`:

| Step | Component | What it does |
|---|---|---|
| 1 Upload | `Step1Upload` | File picker → `POST /api/resume` → stores `resume_id` |
| 2 Job Description | `Step2JD` | JD text/URL input + analysis settings → `POST /api/jd/analyze` |
| 3 Coverage | `Step3Coverage` | Skill coverage table; `+`/`-` feedback buttons → `POST /api/feedback` |
| 4 Review | `Step4Review` | Rewrite suggestions per bullet; accept/edit |
| 5 Export | `Step5Export` | `POST /api/export` → downloads tailored `.docx` |

Steps 3–5 are marked **stale** (yellow) if the JD text changes after an analysis has been run, preventing the user from exporting results based on an outdated analysis.

---

## Database writes

Only two write paths exist:

- **`log_export()`** — called at Step 5 export; writes `jobs`, `resumes`, `cv_pairs`, and `cv_pair_embeddings` atomically
- **`log_feedback()`** — called per `+`/`-` click at Step 3; writes one row to `skill_feedback`

See `docs/db-schema.md` for full schema detail.

---

## Phase 10 — Manual Review Page (replacing Step 4)

### What and why

The current Step 4 shows AI-generated rewrite suggestions (Ollama). This is useful but requires a running LLM and doesn't let users freely edit their resume. Phase 10 replaces Step 4 with a manual editing page where users can directly edit their resume while seeing real-time keyword coverage in a floating side panel.

The old Step 4 (AI suggestions) is preserved as `Step4ReviewLegacy.jsx` but not served in the UI.

### Layout

```
┌───────────────────────────────────┐ ┌──────────────────────┐
│  4) Edit Resume                   │ │ Keyword Coverage  ██░│
│                                   │ │ 23/45 matched        │
│  ── Work Experience ────────────  │ │                      │
│  Software Engineer, Acme Corp     │ │ ✓ Python             │
│  ┌───────────────────────────┐    │ │ ✓ machine learning   │
│  │ Built ML pipeline using...│    │ │ ✗ data governance    │
│  └───────────────────────────┘    │ │ ✗ CI/CD              │
│  ┌───────────────────────────┐    │ │ ~ Kubernetes (ignored│
│  │ Led team of 5 engineers...│    │ │                      │
│  └───────────────────────────┘    │ │                      │
│                                   │ │                      │
│  ── Education ──────────────────  │ │                      │
│  ...                              │ │                      │
│                 [Export →]        │ │                      │
└───────────────────────────────────┘ └──────────────────────┘
                                      ↑ position: sticky
```

- **Left (~65%):** Structured editable resume. Section headers and role titles are read-only labels. Each bullet is an editable text field keyed by `bullet_id`.
- **Right (~30%):** Floating keyword panel (`position: sticky`). Shows all extracted JD keywords with live match status.

### Design decisions

1. **Real-time matching is client-side only.** The floating panel uses case-insensitive `includes()` against the concatenated bullet text. No backend call per keystroke. The backend's semantic matching (embeddings, cosine similarity) is used in Step 3 — Step 4 only needs exact text presence for the visual indicator.

2. **Three keyword states:**
   - **Matched** (green, checkmark) — keyword found in current resume text
   - **Unmatched** (red/default, X mark) — keyword not found
   - **Ignored** (greyed out, strikethrough) — user clicked to dismiss; excluded from progress bar denominator

3. **Users cannot add keywords.** If a user wants a keyword matched, they type it into a bullet. The panel updates instantly. This avoids a split-brain problem about where the source of truth for JD skills lives.

4. **Resume sections are mutable state.** The full `sections` array (from the upload response) is lifted into `App.jsx`. On export, we diff current bullet texts against the originals to build the `acceptedChanges` map that the export endpoint expects.

5. **Step 3 (Coverage) is kept as-is.** It serves as a detailed debug/analysis view with similarity scores and +/- feedback. The new Step 4 is the clean, user-facing editing experience. Step 3 may be hidden in production later.

### New components

| File | Purpose |
|---|---|
| `Step4Edit.jsx` | Two-column layout: editable CV on left, keyword panel on right |
| `KeywordPanel.jsx` | Sticky floating panel: progress bar + keyword list with match/unmatched/ignored states |
| `Step4ReviewLegacy.jsx` | Renamed from `Step4Review.jsx` — preserved but not imported |
