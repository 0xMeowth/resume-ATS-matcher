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
| 4a: Seed script | pending | |
| 4b: Vector search endpoint | pending | |
| 4c: Ollama rewrite integration | pending | |
| 4d: End-to-end RAG flow | pending | |
| 5: PDF accuracy audit | pending | Blocked on real-world usage data |

---

## Phase Order

| Phase | Items | Key Dependency |
|-------|-------|----------------|
| Pre-work | CLAUDE.md + ROADMAP.md | None |
| 1 | Debloat + PDF input | None — do first |
| 2 | FastAPI + React migration | Phase 1 done |
| 3 | SQLite logging DB | Phase 2 done |
| 4 | RAG + Ollama rewrite | Phase 3 + data in DB |
| 5 | PDF parsing accuracy audit & tuning | Phase 1d shipped + real-world usage data |

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

## Phase 4 — RAG + Intelligence

### Stage 4a: Seed script
- Import existing (JD, edited_CV) pairs you already have manually.

### Stage 4b: Vector search endpoint
- `POST /api/jd/similar` — embed new JD's skill terms, query sqlite-vec, return top-K past pairs.

### Stage 4c: Ollama rewrite integration
- Replace `RewriteEngine.generate()` stub with async Ollama call.
- Prompt: given `original_bullet` + `target_keyword` → rewrite bullet.

### Stage 4d: End-to-end RAG flow
- On new JD, auto-suggest the most similar past exported CV as the baseline.
- User can accept or upload their own baseline instead.

---

## Phase 5 — PDF Parsing Accuracy Audit

> Dependency: Phase 1d shipped (basic PDF support). Do this after real-world usage reveals patterns.

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

## Architectural Notes

**JD crawler:** LinkedIn, Greenhouse, Workday, Lever all use SPAs — BeautifulSoup won't work. Scope as a separate optional script requiring Playwright, not a core pipeline dependency. ToS and rate limits apply. **For all phases up to and including Phase 4, use fixed JD text fixtures (pasted or stored as `.txt` files in `tests/fixtures/`) — do not build or depend on a live crawler. The crawler is a Phase 5+ concern.**

**Rewrite engine is a stub:** `rewrite_engine.py` currently generates `"Add keyword: X"`. Step 4 adds near-zero value until Ollama integration (Stage 4c). Be honest about this in README/portfolio writeup.

**EmbeddingEngine caching:** Currently instantiated fresh inside the "Analyze JD" button handler with no `@st.cache_resource`. Becomes a startup singleton in FastAPI — not an issue after Phase 2.

**PDF export:** Exporter writes `.docx` regardless of input format. Surface this clearly in the UI.

**RAG cold-start:** Similarity search is useless without several high-quality (JD, edited_CV) pairs. Run Stage 4a before Stage 4b. Filter by domain/role — cosine similarity alone can match unrelated seniority levels.

**BYO model abstraction:** Ollama first. Only abstract the model interface once 2+ backends are actually working.
