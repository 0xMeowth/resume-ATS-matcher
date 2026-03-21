# Resume ATS Matcher — Roadmap

Tech stack: FastAPI + React, Ollama (local LLM), SQLite + sqlite-vec.

---

## Progress Tracker

> Update this table at the end of every stage. Status: `done` · `in-progress` · `pending` · `skipped`

| Stage | Status | Notes |
|-------|--------|-------|
| Pre-work A: CLAUDE.md staged-work rules | done | |
| Pre-work B: ROADMAP.md created | done | |
| 1a: Delete dead code | done | Deleted `pages/2_Rewrite.py` + `pages/` dir |
| 1b: Debloat `jd_parser.py` | done | Replaced `debug_events` threading with `logger.debug` + `_DebugCapture` handler |
| 1c: Debloat `app.py` | done | No-op — app.py was already clean |
| 1d: PDF input support | done | pdfplumber added; `ResumeData.low_confidence` on `ResumeData`; magic-byte detection; 6 narrow-scope tests; 20/20 passing |
| 2a: API contract doc | done | `docs/api-contract.md` — 3 endpoints: POST /api/resume, POST /api/jd/analyze, POST /api/export. **User did not review the contract but agreed to proceed; revisit if endpoint behaviour feels wrong during Stage 2d smoke-test.** |
| 2b: FastAPI backend scaffold | done | `backend/main.py` (lifespan singletons), `backend/routers.py` (4 endpoints), `backend/stores.py`; imports verified |
| 2c: React frontend scaffold | done | Vite + React; 5-step wizard; `frontend/src/`; build verified |
| 2d: Wire + smoke-test | done | End-to-end flow verified manually |
| 2e: Containerize / deploy config | done | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.dockerignore`; model cache via named volume |
| 3a: Schema + migration script | done | `db/migrate.py` + `db/connection.py`; 3 tables (jobs, resumes, cv_pairs) + 4 indexes; idempotent; verified |
| 3b: DB logging in FastAPI | done | `db/writer.py` log_export(); called from export endpoint; lifespan auto-migrates on startup; integration tested |
| 3c: sqlite-vec extension | done | `cv_pair_embeddings` vec0 virtual table (FLOAT[384]); `_load_vec()` in connection.py; embedding written in log_export(); integration tested |
| 4a: Ollama rewrite integration | done | httpx + asyncio.gather; graceful fallback to stub on Ollama error; 4 tests |
| 5a: Seed script | blocked | Needs real export data in DB first |
| 5b: Vector search endpoint | blocked | Needs seed data |
| 5c: End-to-end RAG flow | blocked | Needs seed data |
| 6: PDF accuracy audit | blocked | Needs real-world usage data |
| 7a: Fix VaR-pattern abbreviation extraction | done | var in allowlist + XxX regex for VaR-pattern abbreviations |
| 7b: Cap noun chunk length at 6 words | done | 6-word cap in _clean_noun_chunk_segment |
| 7c: Restore light_head + domain_stoplist; add noise terms | done | Reverted merge; restored light_head + domain_stoplist; added willingness/engineers/programming to domain_stoplist only |
| 8a: BGE model swap | done | none | BAAI/bge-small-en-v1.5; asymmetric BGE_QUERY_PREFIX for skill + doc embeddings; bullets unprefixed |
| 8b: Feedback schema + API | done | none | skill_feedback table + label index; log_feedback() in writer.py; POST /api/feedback endpoint |
| 8c: Feedback UI | skipped | none | Feedback collection deprioritised; UI commented out, backend intact (endpoint + DB table preserved) |
| 8d: Cross-encoder reranker | done | none | cross-encoder/ms-marco-MiniLM-L-6-v2; opt-in via USE_CROSS_ENCODER=1; sigmoid-normalised scores passed to thresholds |
| 8e: Fine-tune bi-encoder | blocked | none | Needs ~100 skill_feedback rows; builds triplets + MultipleNegativesRankingLoss; saves to .cache/ats_matcher/finetuned_model/ |
| 9a: Text preprocessing (HTML, URLs, emails, slash-compounds) | done | `_preprocess_text()` strips HTML/URLs/emails; slash-compound tokenizer rules; 4 new tests |
| 9b: Exclusion list additions (education, company IDs, qualifications) | done | 16 terms added to domain_stoplist; 2 new tests |
| 9c: Extraction logic fixes (substring suppression, lemmatization, company names) | done | C1: independent phrase survival in `_suppress_substrings`; C2: `_lemma_dedup`; C3: `_extract_company_stopwords`; 3 new tests |
| 9d: MCF dictionary integration (accumulate, load as MCF_SKILL, seed) | done | 782 skills from 134 JDs; `build_mcf_dict.py`; auto-accumulate in `fetch_jds.py`; MCF_SKILL entity ruler |
| 9e: Analysis report + drop JobBERT documentation | done | `docs/test_extraction_comparison.md`; `scripts/extract_legitimate_jobbert.py`; Model Inventory updated |
| 9f: Documentation + custom skill source | done | `config/custom_skills.yaml` (22 terms); CUSTOM_SKILL entity ruler; three-source architecture complete |
| 10a: Wire resume sections into App state | done | `resumeSections` + `originalSectionsRef` in App.jsx; deep-clone for diff |
| 10b: KeywordPanel component | done | Progress bar, keyword list, ignore toggle, 4 states (matched/semantic/unmatched/ignored) |
| 10c: Step4Edit component | done | Two-column flex layout; auto-resize textareas; amber border on semantic bullets |
| 10d: Wire new Step 4 into App.jsx | done | Step4Edit replaces Step4Review; step label "Edit Resume"; diff-based acceptedChanges |
| 10e: CSS for two-column layout + sticky panel | done | Flex layout, sticky panel, keyword state colors, progress bar |
| 10f: Fix layout width | done | `app-wide` class widens to 1200px for Step 4 only |
| 10g: Multi-column keyword flow | done | CSS grid layout for keywords; compact chips; hover-reveal ignore button |
| 10h: Semantic hint state in keyword panel | done | 4th amber state for semantic_strong from Step 3; static, not recomputed |
| 10i: Amber highlight on semantic bullets | done | Amber left border on evidence bullets; tooltip lists matched keywords |
| 10j: Save parsing concern + ROADMAP backlog | done | Memory + backlog item for .docx wrapped bullet parsing bug |
| 11a: Fetch test fixtures + baseline | done | 6 PDF resumes downloaded; baseline JSON + FAILURE_MODES.md |
| 11b: Rich PDF extraction (Line dataclass) | done | `_extract_lines_from_pdf()` with word-level x0/font_size/bold/bullet/y_gap |
| 11c: Multi-signal heading detection (PDF) | done | 5 signals: font size, bold, keyword, ALL-CAPS, y_gap; ≥2 agree or font ≥4pt |
| 11d: Indentation-aware bullet + continuation (PDF) | done | x0 clustering; continuation merging; sub-bullet (∗) support |
| 11e: Port fixes to DOCX path | done | Continuation merging via `_is_continuation()`; keyword heading detection |
| 11f: Regression tests | done | 15 new tests with real PDF fixtures; 48 total passing |
| 11g: Update ROADMAP + cleanup | done | Phase 11 stages added; backlog removed |

---

## Phase Order

| Phase | Items | Key Dependency |
|-------|-------|----------------|
| Pre-work | CLAUDE.md + ROADMAP.md | None |
| 1 | Debloat + PDF input | None — do first |
| 2 | FastAPI + React migration | Phase 1 done |
| 3 | SQLite logging DB | Phase 2 done |
| 4 | Ollama rewrite | Phase 3 done |
| 5 (blocked) | RAG + similarity search | Phase 3 done + real usage data in DB |
| 6 | PDF parsing accuracy audit | Phase 1d shipped + real-world usage data |
| 9 | spaCy extraction quality (preprocessing, stopwords, logic fixes, MCF dictionary) | Phase 7/8 done; discovered via 20-JD comparison |
| 10 | Manual review page (replace Step 4 with editable CV + floating keyword panel) | Phase 9 done |
| 11 | Resume parsing robustness (PDF-first: rich extraction, multi-signal headings, continuation merging) | Phase 10 done |

Within-phase parallelism:
- Phase 1: Debloat and PDF support are independent.
- Phase 2: FastAPI backend and React frontend can be built in parallel once the API contract (Stage 2a) is defined.

---

## Phase 1 — Clean House

### Stage 1a: Delete dead code
- Confirm `pages/2_Rewrite.py` is dead/unused, then delete it.
- Remove any leftover Streamlit multi-page scaffolding.
- **Verification:** `uv run python -m compileall src app.py main.py`

### Stage 1b: Debloat `jd_parser.py` — remove debug_events threading
- Replace the `debug_events: Optional[List[Dict[str, str]]]` parameter pattern across all private methods in `jd_parser.py` with `logging.debug(...)` calls.
- `extract_skill_components(debug=True)` can stay as the public API surface but internally sets `logging.getLogger(__name__).setLevel(logging.DEBUG)` rather than building a list.
- The Streamlit debug table in `app.py` can attach a `logging.handlers.MemoryHandler` or a list-based handler if the debug UI is still needed.
- **Verification:** `uv run pytest tests/test_jd_parser.py`

### Stage 1c: Debloat `app.py`
- Audit for debug scaffolding, leftover commented code, or session-state keys from the multi-page experiment.
- **Verification:** `uv run streamlit run app.py` (manual smoke check)

### Stage 1d: PDF input support (narrow scope)
- Add `pdfplumber` dependency: `uv add pdfplumber`
- Modify `resume_parser.py` to detect `.pdf` vs `.docx` by MIME type / file magic bytes (not extension).
- Return a `low_confidence` flag on `ResumeData` for PDF input; surface a warning in the UI.
- Export remains `.docx` regardless of input — document this in the UI.
- Update `app.py` file uploader to accept `["docx", "pdf"]`.
- Tests: narrow scope only — verify the parser doesn't crash and returns `low_confidence=True` for PDF. No accuracy assertions.
- **Verification:** `uv run pytest tests/` + manual upload of a sample PDF

> **Note:** PDF parsing accuracy is out of scope for Phase 1. pdfplumber output will have formatting noise (merged lines, lost bullet structure, inconsistent spacing). A dedicated accuracy audit and tuning pass is scheduled in Phase 5 below.

---

## Phase 2 — Architecture Shift (FastAPI + React)

### Stage 2a: Define API contract
- Write `docs/api-contract.md` with all endpoints, request/response shapes.
- No code yet — align with user before building.

### Stage 2b: FastAPI backend scaffold
- Create `backend/` with FastAPI app; lifespan-managed singletons for `EmbeddingEngine` and `JDParser`.
- Implement upload + analyze endpoints; keep business logic in `src/ats_matcher/` unchanged.

### Stage 2c: React frontend scaffold
- Vite + React, minimal dependencies.
- Implement the 5-step wizard matching the current Streamlit flow.

### Stage 2d: Wire and smoke-test
- Connect frontend to backend; verify end-to-end flow.

### Stage 2e: Containerize / deploy config
- `docker-compose.yml` for local; environment-based config for Railway.

---

## Phase 3 — Persistence (SQLite + sqlite-vec)

### Stage 3a: Schema + migration script
```sql
jobs     (id, created_at, jd_url, jd_text, jd_skill_terms JSON)
resumes  (id, filename, file_bytes BLOB, format)
cv_pairs (id, job_id, baseline_resume_id, exported_docx BLOB, accepted_changes JSON, created_at)
```

### Stage 3b: Integrate logging into FastAPI endpoints
- Write to DB on export (after user accepts changes).

### Stage 3c: Add sqlite-vec extension
- Add vector column to `cv_pairs` for JD skill embeddings (used in Phase 4).

---

## Phase 4 — Ollama Rewrite

### Stage 4a: Ollama rewrite integration
- Replace `RewriteEngine.generate()` stub with async Ollama call.
- Prompt: given `original_bullet` + `target_keyword` → rewrite bullet.
- Surface generated rewrites in Step 4 of the React wizard.

---

## Phase 5 — RAG + Similarity Search

> **BLOCKED:** Do not start until real (JD, edited_CV) export pairs exist in the DB. Cold-start makes similarity search useless without seed data.

### Stage 5a: Seed script
- Export several real (JD, edited_CV) pairs through the app first.
- Optionally write a one-off import script for existing pairs.

### Stage 5b: Vector search endpoint
- `POST /api/jd/similar` — embed new JD's skill terms, query sqlite-vec, return top-K past pairs.
- Filter candidates by role/domain to avoid seniority-level mismatches.

### Stage 5c: End-to-end RAG flow
- On new JD, auto-suggest the most similar past exported CV as the baseline.
- User can accept the suggestion or upload their own baseline instead.

---

## Phase 7 — Extraction Quality Fixes

Identified via live JD analysis (finance internship JD × real resume). These are precision/noise fixes to the spaCy extraction pipeline — independent of the model swap (Phase 8).

### Stage 7a: Fix VaR-pattern abbreviation extraction
- Add `var` to `single_token_allowlist` in `config/skill_extraction.yaml`
- Extend `_allow_single_token` in `jd_parser.py` to accept 3-char words where pos 0 and 2 are uppercase and pos 1 is not (e.g. VaR, DoS)
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

### Stage 7b: Cap noun chunk length at 6 words
- In `_clean_noun_chunk_segment`, return `None` if `len(candidate.split()) > 6`
- Eliminates sentence-length "skill terms" like "Web3 AI powered financial token risk control system"
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

### Stage 7c: Restore light_head + domain_stoplist; add noise terms
- Reverted an earlier merge of `light_head` + `domain_stoplist` into `generic_nouns` (conflating them caused regressions, e.g. "functional programming" → head stripped → "functional" dropped)
- Restored both YAML keys with original entries; added `willingness`, `engineers`, `programming` to `domain_stoplist` only (not `light_head`)
- Restored `light_head: set[str]` and `domain_stoplist: set[str]` fields in `SkillExtractionConfig`
- Updated `jd_parser.py` to use `self.light_head` for head-stripping and `self.domain_stoplist` for candidate rejection
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

---

## Phase 8 — Coverage Quality Improvements

### Stage 8a: BGE model swap
- Replace `all-MiniLM-L6-v2` with `BAAI/bge-small-en-v1.5` (same 384-dim, drop-in replacement).
- Add `prefix` param to `EmbeddingEngine.embed()`; apply `BGE_QUERY_PREFIX` to skill + doc embeddings (query side); bullets stay unprefixed (passage side).
- **Verification:** `uv run pytest tests/ -x -q`

### Stage 8b: Feedback schema + API
- Add `skill_feedback` table + label index to `db/migrate.py`.
- Add `log_feedback()` to `db/writer.py`.
- Add `FeedbackRequest` model and `POST /api/feedback` endpoint to `backend/routers.py`.
- **Verification:** `uv run pytest tests/ -x -q` then manually POST to `/api/feedback` and check DB row.

### Stage 8c: Feedback UI
- Add `+`/`-` buttons per row in Coverage tab (`Step3Coverage.jsx`); fire `POST /api/feedback`; toggle local state (deselect on second click).
- Thread `analysisId` prop from `App.jsx`; add `submitFeedback()` to `api.js`.
- **Verification:** Manual smoke test — click buttons, verify row in `skill_feedback` via `sqlite3 data/ats_matcher.db "SELECT * FROM skill_feedback LIMIT 5;"`.

### Stage 8d: Cross-encoder reranker
- Add optional `cross_encoder` param to `MatchingEngine`; if set, re-score bi-encoder shortlist with `CrossEncoder.predict()` + sigmoid normalisation.
- Load `cross-encoder/ms-marco-MiniLM-L-6-v2` in `backend/main.py` lifespan, gated on `USE_CROSS_ENCODER=1`.
- **Verification:** `USE_CROSS_ENCODER=1 uv run pytest tests/ -x -q`

### Stage 8e: Fine-tune bi-encoder
> **BLOCKED:** Do not start until ~100 `skill_feedback` rows exist from real usage.
- New script `scripts/finetune_embeddings.py`: read `skill_feedback`, build `InputExample` triplets, fine-tune with `MultipleNegativesRankingLoss`, save to `.cache/ats_matcher/finetuned_model/`.
- Update `EmbeddingEngine` default model path to fine-tuned model after training.
- **Verification:** Run script, check loss curve, spot-check similarity on held-out pairs before/after.

---

## Phase 6 — PDF Parsing Accuracy Audit

> Dependency: Phase 1d shipped (basic PDF support). Do this after real-world usage reveals patterns. Formerly Phase 5.

Known issues to investigate and tune:
- **Merged lines:** pdfplumber may concatenate adjacent columns or header/footer text into bullets.
- **Lost bullet structure:** PDF bullets often lose their list markers and become flat paragraphs; the section/role/bullet hierarchy from `resume_parser.py` may degrade significantly.
- **Inconsistent spacing:** Extra whitespace, hyphenation artifacts, and Unicode dashes need normalisation.
- **Multi-column layouts:** Common in designer resumes; pdfplumber reads columns left-to-right by bounding box, which can interleave unrelated text.

Suggested audit approach:
1. Collect 5–10 real PDF resumes spanning different formats (single-column, two-column, designer, plain).
2. Run `resume_parser.py` on each and inspect `ResumeData` structure manually.
3. Record failure modes and write targeted fixes or post-processing heuristics in `resume_parser.py`.
4. Add accuracy regression tests for each fixed failure mode.

---

## Phase 9 — spaCy Extraction Quality Improvements

> Discovered via 20-JD comparison (spaCy vs JobBERT vs MCF platform skills). JDs fetched from MyCareersFuture API contain raw HTML — previous testing used pasted text and never caught these issues.

### Stage 9a: Text Preprocessing
- A1: Strip HTML tags from ALL input text (not just URL-fetched)
- A2: Remove URLs (`https?://\S+`)
- A3: Remove email addresses (`\S+@\S+\.\S+`)
- A4: Preserve slash-compounds as single tokens (e.g. `CI/CD`) via spaCy tokenizer exceptions
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

### Stage 9b: Exclusion List Additions
- B1: Education terms (`bachelor`, `bachelors`, `bachelor's`, `master`, `masters`, `master's`, `phd`, `diploma`, `degree`, `education`)
- B2: Company identifiers (`pte`, `ltd`)
- B3: Qualification terms (`qualification`, `qualifications`)
- B4: Misc noise (`diverse`)
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

### Stage 9c: Extraction Logic Fixes
- C1: Substring suppression — allow shorter substrings to survive if they appear independently in the JD
- C2: Lemmatize for dedup only (keep original surface form) — collapses `strategy frameworks` / `strategy framework` without changing displayed text
- C3: Company name removal — parse `Company:` header from fetch script, add tokens to per-JD stoplist
- C4: Investigate why "software architecture design" is missed (likely substring suppression)
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

### Stage 9d: MCF Dictionary Integration
- D0: Fetch baseline MCF data (25 × 6 categories → `data/mcf_jds/`)
- D1: Build MCF dictionary from all `.mcf.txt` files → `config/mcf_skills.json`
- D2: Auto-accumulate on future fetches (modify `fetch_jds.py`)
- D3: Load MCF dictionary in `jd_parser.py` as `MCF_SKILL` entity ruler
- D4: (deferred) Seed with more industry diversity
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

### Stage 9e: Analysis Report
- E1: Extract legitimate jobbert-only skills from `comparison.csv` → `tests/claude_analyse_rest_txt_before.csv`
- E2: Update ROADMAP.md Model Inventory to mark JobBERT as evaluated and dropped
- **Verification:** File exists and contains deduplicated legitimate skill list

### Stage 9f: Documentation + Custom Skill Source
- F1: Write `docs/test_extraction_comparison.md` — methodology, scripts, results, root causes (done)
- F2: Create `config/custom_skills.yaml` — third skill source seeded with high-confidence terms from root cause analysis
- F3: Load custom skills in `jd_parser.py` as `CUSTOM_SKILL` entity ruler patterns
- **Verification:** `uv run pytest tests/test_jd_parser.py -x -q`

Three-source architecture:
| Source | Label | File | Growth mechanism |
|---|---|---|---|
| ESCO | `ESCO_SKILL` | `.cache/ats_matcher/esco/` | EU API (static, versioned) |
| MCF | `MCF_SKILL` | `config/mcf_skills.json` | Auto-accumulated from `fetch_jds.py` |
| Custom | `CUSTOM_SKILL` | `config/custom_skills.yaml` | Manually curated — analysis findings, user additions |

---

## Phase 10 — Manual Review Page

> Replaces Step 4 (AI rewrite suggestions) with a manual CV editing page + floating keyword panel. Old Step 4 preserved as `Step4ReviewLegacy.jsx`.

### Stage 10a: Wire resume sections into App state
- Capture `sections` from upload response in `App.jsx` (currently discarded)
- Store as `resumeSections` + `originalSections` (ref for diff at export)
- **Verification:** Upload a resume, check sections in React DevTools

### Stage 10b: KeywordPanel component
- Floating panel: progress bar (X/Y matched) + keyword list
- Three states: matched (green), unmatched (red), ignored (grey strikethrough)
- Ignore toggle per keyword; ignored excluded from progress denominator
- Sorted: unmatched first, then matched, then ignored
- **Verification:** Render with mock data, toggle ignore, verify counts

### Stage 10c: Step4Edit component
- Two-column flex layout: editable CV left (~65%), KeywordPanel right (~30%)
- Section headers + role titles as read-only labels, bullets as editable fields
- Real-time matching: on each keystroke, concatenate all bullets, run client-side `includes()` check
- **Verification:** Edit a bullet, see keyword panel update in real-time

### Stage 10d: Wire new Step 4 into App.jsx
- Import `Step4Edit` instead of `Step4Review`; rename STEPS[3] to `'Edit Resume'`
- Pass `resumeSections`, `skillMatches`, `onSectionsChange`, `onDone`
- On export: diff current vs original bullet texts → build `acceptedChanges` map
- **Verification:** Full flow: upload → analyze → edit → export downloads .docx

### Stage 10e: CSS for layout + sticky panel
- `.edit-layout` flex container, `.keyword-panel` sticky positioning
- Keyword state colors, progress bar, section/role header styles
- **Verification:** Panel stays visible on scroll, layout doesn't break

---

## Model Inventory

| Model | Category | Size | Purpose |
|---|---|---|---|
| `spacy en_core_web_sm` | Extraction | ~12 MB | Tokenization, POS tagging, noun chunks, NER |
| `bge-small-en-v1.5` | Matching | 133 MB | Bi-encoder embeddings for skill → bullet similarity |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Matching (reranker) | ~85 MB | Re-scores bi-encoder shortlist; optional via `USE_CROSS_ENCODER=1` |
| Ollama llama3.2 | Rewrite | ~2 GB | Generates bullet rewrite suggestions |
| `jjzha/jobbert_knowledge_extraction` _(evaluated, dropped)_ | Extraction | ~410 MB | Evaluated via 20-JD comparison: 86% noise, 0% MCF validation, 124 legitimate skills out of 1,150 extractions. Legitimate finds better addressed by MCF dictionary + ESCO augmentation. |

**Current total:** ~2.2 GB &nbsp;|&nbsp; **Hard limit:** 4 GB (no GPU assumed)

---

## Architectural Notes

**JD crawler:** LinkedIn, Greenhouse, Workday, Lever all use SPAs — BeautifulSoup won't work. Scope as a separate optional script requiring Playwright, not a core pipeline dependency. ToS and rate limits apply. **For all phases up to and including Phase 5, use fixed JD text fixtures (pasted or stored as `.txt` files in `tests/fixtures/`) — do not build or depend on a live crawler. The crawler is a Phase 6+ concern.**

**Rewrite engine is a stub:** `rewrite_engine.py` currently generates `"Add keyword: X"`. Step 4 adds near-zero value until Ollama integration (Stage 4a). Be honest about this in README/portfolio writeup.

**EmbeddingEngine caching:** Currently instantiated fresh inside the "Analyze JD" button handler with no `@st.cache_resource`. Becomes a startup singleton in FastAPI — not an issue after Phase 2.

**PDF export:** Exporter writes `.docx` regardless of input format. Surface this clearly in the UI.

**RAG cold-start:** Similarity search is useless without several high-quality (JD, edited_CV) pairs. Run Stage 4a before Stage 4b. Filter by domain/role — cosine similarity alone can match unrelated seniority levels.

**BYO model abstraction:** Ollama first. Only abstract the model interface once 2+ backends are actually working.

