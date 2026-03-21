"""
Run this script once to create (or verify) the ATS Matcher database schema.
Idempotent — safe to re-run on an existing database.

Usage:
    uv run python db/migrate.py
    ATS_DB_PATH=/path/to/custom.db uv run python db/migrate.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Ensure project root is on sys.path so `db` is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import get_connection, get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    jd_url      TEXT,
    jd_text     TEXT NOT NULL,
    jd_skill_terms TEXT NOT NULL  -- JSON array of ranked skill terms
);

CREATE TABLE IF NOT EXISTS resumes (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    filename    TEXT NOT NULL,
    file_bytes  BLOB NOT NULL,
    format      TEXT NOT NULL     -- 'docx' or 'pdf'
);

CREATE TABLE IF NOT EXISTS cv_pairs (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    job_id              TEXT NOT NULL REFERENCES jobs(id),
    baseline_resume_id  TEXT NOT NULL REFERENCES resumes(id),
    exported_docx       BLOB NOT NULL,
    accepted_changes    TEXT NOT NULL  -- JSON object {bullet_id: new_text}
);

CREATE INDEX IF NOT EXISTS idx_cv_pairs_job_id      ON cv_pairs(job_id);
CREATE INDEX IF NOT EXISTS idx_cv_pairs_resume_id   ON cv_pairs(baseline_resume_id);
CREATE INDEX IF NOT EXISTS idx_cv_pairs_created_at  ON cv_pairs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at      ON jobs(created_at);

CREATE TABLE IF NOT EXISTS skill_feedback (
    id           TEXT PRIMARY KEY,
    analysis_id  TEXT,
    skill_phrase TEXT NOT NULL,
    bullet_text  TEXT,
    label        TEXT NOT NULL,   -- 'covered' or 'not_covered'
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_feedback_label ON skill_feedback (label);
"""

# Separate schema for the vec0 virtual table — requires sqlite-vec to be loaded.
# Applied after BASE_SCHEMA; silently skipped if extension is unavailable.
_VEC_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS cv_pair_embeddings USING vec0(
    cv_pair_id TEXT PRIMARY KEY,
    jd_embedding FLOAT[384]
);
"""


def apply_schema(conn: sqlite3.Connection) -> None:
    """Apply schema to an open connection. Idempotent."""
    conn.executescript(SCHEMA)
    try:
        conn.executescript(_VEC_SCHEMA)
    except Exception:
        pass  # sqlite-vec not available; vec table skipped
    conn.commit()


def migrate() -> None:
    db_path = get_db_path()
    print(f"Migrating database at: {db_path}")
    conn = get_connection()
    try:
        apply_schema(conn)
        print("Migration complete.")
        _print_tables(conn)
    finally:
        conn.close()


def _print_tables(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"Tables: {[r['name'] for r in rows]}")


if __name__ == "__main__":
    migrate()
