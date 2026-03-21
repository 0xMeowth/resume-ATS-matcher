# Database Schema

SQLite database managed by `db/migrate.py`. Default path: `ats_matcher.db` (project root), overridable via `ATS_DB_PATH`.

Run migrations:
```bash
uv run python db/migrate.py
```

---

## Tables

### `jobs`

One row per JD analyzed.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | UUID |
| `created_at` | TEXT | ISO 8601 |
| `jd_url` | TEXT | Nullable — set if JD was fetched from a URL |
| `jd_text` | TEXT | Raw JD text |
| `jd_skill_terms` | TEXT | JSON array of ranked skill terms extracted by `jd_parser.py` |

---

### `resumes`

One row per uploaded resume file.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | UUID |
| `created_at` | TEXT | ISO 8601 |
| `filename` | TEXT | Original upload filename |
| `file_bytes` | BLOB | Raw file content |
| `format` | TEXT | `'docx'` or `'pdf'` |

---

### `cv_pairs`

One row per completed export — links a job and a resume, captures the user's accepted rewrites.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | UUID |
| `created_at` | TEXT | ISO 8601 |
| `job_id` | TEXT FK → `jobs.id` | |
| `baseline_resume_id` | TEXT FK → `resumes.id` | The original resume before edits |
| `exported_docx` | BLOB | Final `.docx` with accepted changes applied |
| `accepted_changes` | TEXT | JSON object `{bullet_id: new_text}` — only bullets the user accepted |

Indexes: `job_id`, `baseline_resume_id`, `created_at`.

**Phase 5 dependency:** `cv_pairs` rows are the seed data for RAG similarity search (Stage 5a–5c). Vector search is useless until real export pairs accumulate through normal usage.

---

### `skill_feedback`

One row per `+`/`-` click in the Coverage tab. Feeds the bi-encoder fine-tuning pipeline (Stage 8e).

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | UUID |
| `analysis_id` | TEXT | Links back to the analysis session (nullable) |
| `skill_phrase` | TEXT | The skill term being judged |
| `bullet_text` | TEXT | The resume bullet it was matched against (nullable) |
| `label` | TEXT | `'covered'` or `'not_covered'` |
| `created_at` | TEXT | ISO 8601 |

Index: `label`.

**Fine-tuning threshold:** ~100 rows for meaningful threshold calibration; ~500+ rows for genuine recall improvement via `MultipleNegativesRankingLoss`.

---

### `cv_pair_embeddings` (virtual)

sqlite-vec virtual table. One row per `cv_pairs` row — stores the 384-dim JD embedding for nearest-neighbour search.

| Column | Type | Notes |
|---|---|---|
| `cv_pair_id` | TEXT PK | References `cv_pairs.id` |
| `jd_embedding` | FLOAT[384] | Encoded with `BAAI/bge-small-en-v1.5` + BGE query prefix |

Requires the `sqlite-vec` extension to be loaded (`db/connection.py` handles this). Silently skipped during migration if the extension is unavailable.

---

## Writers

All DB writes go through `db/writer.py`:

- `log_export()` — writes to `jobs`, `resumes`, `cv_pairs`, and `cv_pair_embeddings` atomically on export
- `log_feedback()` — writes a single row to `skill_feedback`
