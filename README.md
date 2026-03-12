# Resume ATS Matcher

Human-in-the-loop resume tailoring tool. Upload a `.docx` or `.pdf` resume, paste a job description, get a keyword coverage report and rewrite suggestions, accept edits, and download a tailored `.docx`.

---

## Running the app

There are two ways to run it: **Docker Compose** (recommended, no Python/Node setup required) or **locally** (two separate processes).

### Option A — Docker Compose

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

- Frontend: http://localhost
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

> **First run is slow.** The backend downloads the spaCy model at build time and the HuggingFace sentence-transformer model (~400 MB) on first use. Both are cached in a Docker volume — subsequent starts are fast.

To stop:
```bash
docker compose down
```

To wipe the model cache (forces re-download):
```bash
docker compose down -v
```

---

### Option B — Local (dev mode)

#### Prerequisites

- Python 3.11–3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 18+

#### Setup (once)

```bash
# Python deps + editable package install
uv sync
uv pip install -e .
uv run python -m spacy download en_core_web_sm

# Frontend deps
cd frontend && npm install && cd ..
```

#### Run

Open two terminals:

**Terminal 1 — backend:**
```bash
uv run uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — frontend:**
```bash
cd frontend && npm run dev
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

> The Vite dev server proxies `/api/*` to the backend automatically — no CORS issues.

---

## Testing the API directly

With the backend running (`--reload` or Docker), hit the Swagger UI at http://localhost:8000/docs or use curl:

### 1. Health check
```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

### 2. Upload a resume
```bash
curl -X POST http://localhost:8000/api/resume \
  -F "file=@/path/to/your_resume.docx"
# {"resume_id":"a1b2c3d4","low_confidence":false,"sections":[...]}
```

### 3. Analyze a job description
```bash
curl -X POST http://localhost:8000/api/jd/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_id": "a1b2c3d4",
    "jd_text": "We are looking for a Senior ML Engineer with Python, PyTorch, and Kubernetes experience.",
    "settings": {
      "max_skill_terms": 120,
      "skill_ranker": "mmr",
      "skill_matching": "embedding"
    }
  }'
# {"analysis_id":"x9y8z7w6","skill_matches":[...],"rewrite_suggestions":[...]}
```

### 4. Export with accepted changes
```bash
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -d '{
    "resume_id": "a1b2c3d4",
    "analysis_id": "x9y8z7w6",
    "accepted_changes": {
      "exp-role-0": "Built ML pipelines using PyTorch and Kubernetes"
    }
  }' \
  --output tailored_resume.docx
```

Full API contract: [`docs/api-contract.md`](docs/api-contract.md)

---

## Running tests

```bash
uv run pytest                          # all tests
uv run pytest tests/test_jd_parser.py  # JD parser only
uv run pytest tests/test_resume_parser.py  # resume parser (PDF + docx)
uv run pytest -v                       # verbose
```

---

## How it works

5-step pipeline:

1. **Parse resume** — detects `.docx` vs `.pdf` by magic bytes; extracts sections → roles → bullets with stable IDs
2. **Parse JD** — spaCy (`en_core_web_sm`) + ESCO entity ruler extracts skill candidates; configurable stoplist and allowlist
3. **Rank & embed** — TF-IDF, MMR, or Hybrid ranking selects top-K skill terms; `all-MiniLM-L6-v2` encodes skills and bullets
4. **Match** — classifies each skill as `exact`, `semantic_strong`, `semantic_weak`, or `missing`; stub rewrite hints generated
5. **Export** — user-accepted bullet edits applied back to the original `.docx`

> **Note:** The rewrite engine currently generates placeholder hints ("Add keyword: X"). Ollama-based rewrites are planned for Phase 4.
> **Note:** PDF input sets a `low_confidence` flag — parsing accuracy is lower than `.docx`. A full PDF accuracy audit is planned for Phase 5.

---

## Project layout

```
backend/          FastAPI app (main.py, routers.py, stores.py)
frontend/         Vite + React 5-step wizard
src/ats_matcher/  Core business logic (parser, embedder, matcher, exporter)
config/           Skill extraction config (stopwords, allowlists)
tests/            Pytest test suite
docs/             API contract
ROADMAP.md        Phase plan and progress tracker
```
