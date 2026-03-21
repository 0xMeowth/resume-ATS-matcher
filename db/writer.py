from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np

from backend.stores import AnalysisEntry, ResumeEntry, new_id
from db.connection import get_connection


def _now() -> str:
    return datetime.now(UTC).isoformat()


def log_feedback(
    analysis_id: str,
    skill_phrase: str,
    bullet_text: str | None,
    label: str,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO skill_feedback (id, analysis_id, skill_phrase, bullet_text, label, created_at) VALUES (?,?,?,?,?,?)",
            (str(uuid4()), analysis_id, skill_phrase, bullet_text, label, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def log_export(
    resume_id: str,
    resume_entry: ResumeEntry,
    analysis_entry: AnalysisEntry,
    exported_docx: bytes,
    accepted_changes: dict[str, str],
) -> str:
    """Write one export event to the DB. Returns the new cv_pair id."""
    fmt = "pdf" if resume_entry.resume_data.low_confidence else "docx"
    skill_terms = [m.phrase for m in analysis_entry.skill_matches]

    job_id = new_id()
    cv_pair_id = new_id()
    now = _now()

    conn = get_connection()
    try:
        with conn:
            # Resume — INSERT OR IGNORE so re-uploads of the same session don't duplicate
            conn.execute(
                """
                INSERT OR IGNORE INTO resumes (id, created_at, filename, file_bytes, format)
                VALUES (?, ?, ?, ?, ?)
                """,
                (resume_id, now, resume_entry.filename, resume_entry.file_bytes, fmt),
            )

            conn.execute(
                """
                INSERT INTO jobs (id, created_at, jd_url, jd_text, jd_skill_terms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    now,
                    analysis_entry.jd_url,
                    analysis_entry.jd_text,
                    json.dumps(skill_terms),
                ),
            )

            conn.execute(
                """
                INSERT INTO cv_pairs
                  (id, created_at, job_id, baseline_resume_id, exported_docx, accepted_changes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cv_pair_id,
                    now,
                    job_id,
                    resume_id,
                    exported_docx,
                    json.dumps(accepted_changes),
                ),
            )

            if analysis_entry.doc_embedding is not None:
                embedding_blob = analysis_entry.doc_embedding.astype(np.float32).tobytes()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cv_pair_embeddings (cv_pair_id, jd_embedding)
                    VALUES (?, ?)
                    """,
                    (cv_pair_id, embedding_blob),
                )
    finally:
        conn.close()

    return cv_pair_id
