# API Contract — Resume ATS Matcher

> Stage 2a. No code yet — this document must be agreed on before backend scaffold begins (Stage 2b).
>
> All endpoints are prefixed `/api`. All request/response bodies are JSON unless noted.
> Errors follow a single envelope: `{ "detail": "<message>" }` with an appropriate HTTP status code.

---

## Endpoints

### `GET /api/health`

Liveness check.

**Response `200`**
```json
{ "status": "ok" }
```

---

### `POST /api/resume`

Upload and parse a resume file. Stores the raw bytes server-side for use in export.

**Request** — `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | binary | yes | `.docx` or `.pdf`; detected by magic bytes, not extension |

**Response `200`**
```json
{
  "resume_id": "a1b2c3d4",
  "low_confidence": false,
  "sections": [
    {
      "title": "EXPERIENCE",
      "roles": [
        {
          "title": "Senior Engineer | Acme Corp | 2021–2024",
          "bullets": [
            { "bullet_id": "exp-role-0", "text": "Built distributed systems serving 10M users" }
          ]
        }
      ]
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `resume_id` | string | Opaque ID; required for all subsequent requests |
| `low_confidence` | bool | `true` if input was PDF |
| `sections` | array | Mirrors `ResumeData.sections`; each bullet includes its `bullet_id` |

**Errors**

| Status | Condition |
|--------|-----------|
| `400` | File is not a valid `.docx` or `.pdf` |
| `422` | No file attached |

---

### `POST /api/jd/analyze`

Extract skill terms from a JD, rank them, embed, and match against the parsed resume. Also generates rewrite suggestions. This is the heavy step — runs NLP, embedding, and matching.

**Request**
```json
{
  "resume_id": "a1b2c3d4",
  "jd_text": "We are looking for a Senior ML Engineer...",
  "jd_url": null,
  "settings": {
    "max_skill_terms": 120,
    "skill_ranker": "mmr",
    "mmr_diversity": 0.3,
    "skill_matching": "embedding",
    "rerank_top_k": 15,
    "skill_strong_threshold": 0.7,
    "skill_weak_threshold": 0.55,
    "debug": false
  }
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `resume_id` | string | yes | — | Must match a previously uploaded resume |
| `jd_text` | string\|null | one of jd_text/jd_url | — | Raw JD text |
| `jd_url` | string\|null | one of jd_text/jd_url | — | URL to fetch JD from; see crawler note in ROADMAP.md — use `jd_text` in all phases ≤ 4 |
| `settings.max_skill_terms` | int | no | `120` | |
| `settings.skill_ranker` | `"mmr"` \| `"tfidf"` \| `"hybrid"` | no | `"mmr"` | |
| `settings.mmr_diversity` | float 0–1 | no | `0.3` | Ignored when `skill_ranker` is `"tfidf"` |
| `settings.skill_matching` | `"embedding"` \| `"tfidf_rerank"` | no | `"embedding"` | |
| `settings.rerank_top_k` | int | no | `15` | Ignored unless `skill_matching` is `"tfidf_rerank"` |
| `settings.skill_strong_threshold` | float | no | `0.7` | |
| `settings.skill_weak_threshold` | float | no | `0.55` | |
| `settings.debug` | bool | no | `false` | If `true`, response includes `debug_events` |

**Response `200`**
```json
{
  "analysis_id": "x9y8z7w6",
  "skill_matches": [
    {
      "phrase": "machine learning",
      "match_type": "exact",
      "similarity": 1.0,
      "evidence_bullet_id": "exp-role-0",
      "evidence_text": "Built ML pipelines..."
    }
  ],
  "rewrite_suggestions": [
    {
      "bullet_id": "exp-role-1",
      "phrase": "kubernetes",
      "original_text": "Managed container orchestration",
      "suggestion_text": "Add keyword: kubernetes"
    }
  ],
  "debug_events": null
}
```

| Field | Type | Notes |
|-------|------|-------|
| `analysis_id` | string | Opaque ID; required for export |
| `skill_matches` | array | One entry per ranked skill term; `match_type` is one of `exact`, `semantic_strong`, `semantic_weak`, `missing` |
| `rewrite_suggestions` | array | Only for non-exact matches; may be empty |
| `debug_events` | array\|null | Populated only when `settings.debug` is `true` |

**Errors**

| Status | Condition |
|--------|-----------|
| `404` | `resume_id` not found |
| `400` | Both `jd_text` and `jd_url` are null/empty |

---

### `POST /api/export`

Apply accepted changes to the resume and return a `.docx` file. This is the write-to-DB trigger in Phase 3.

**Request**
```json
{
  "resume_id": "a1b2c3d4",
  "analysis_id": "x9y8z7w6",
  "accepted_changes": {
    "exp-role-1": "Managed container orchestration with Kubernetes"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `resume_id` | string | yes | |
| `analysis_id` | string | yes | Used in Phase 3 to log the (JD, CV) pair to DB |
| `accepted_changes` | object | yes | Map of `bullet_id → new_text`; may be empty `{}` to export with no changes |

**Response `200`** — binary `.docx`

```
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="tailored_resume.docx"
```

**Errors**

| Status | Condition |
|--------|-----------|
| `404` | `resume_id` or `analysis_id` not found |

---

## Server-side state

The backend holds two in-memory stores (upgraded to DB in Phase 3):

| Store | Key | Value | Lifetime |
|-------|-----|-------|----------|
| `resume_store` | `resume_id` | raw file bytes + `ResumeData` | process lifetime (Phase 2); DB row (Phase 3+) |
| `analysis_store` | `analysis_id` | `skill_matches` + `rewrite_suggestions` + `jd_text` | same |

IDs are random hex strings (e.g. `secrets.token_hex(8)`). No auth in Phase 2 — single-user local tool.

---

## Singletons (lifespan-managed)

| Object | Notes |
|--------|-------|
| `JDParser` | Loads spaCy model + ESCO ruler once at startup |
| `EmbeddingEngine` | Loads `all-MiniLM-L6-v2` once at startup |

Both are instantiated in the FastAPI `lifespan` context and injected via `app.state`.

---

## What this contract does NOT cover (yet)

- Authentication / multi-user sessions
- `POST /api/jd/similar` (Phase 4 — vector search)
- Streaming responses for long-running analysis (potential future improvement)
- Rate limiting
