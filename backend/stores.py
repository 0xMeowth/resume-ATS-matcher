from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ats_matcher.models import PhraseMatch, ResumeData, RewriteSuggestion


@dataclass
class ResumeEntry:
    file_bytes: bytes
    resume_data: ResumeData
    filename: str


@dataclass
class AnalysisEntry:
    resume_id: str
    jd_text: str
    jd_url: str | None
    skill_matches: list[PhraseMatch]
    rewrite_suggestions: list[RewriteSuggestion]
    doc_embedding: Optional[np.ndarray] = None
    injection_hints: Optional[dict] = None


def new_id() -> str:
    return secrets.token_hex(8)
