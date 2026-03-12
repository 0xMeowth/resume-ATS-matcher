from __future__ import annotations

import secrets
from dataclasses import dataclass

from ats_matcher.models import PhraseMatch, ResumeData, RewriteSuggestion


@dataclass
class ResumeEntry:
    file_bytes: bytes
    resume_data: ResumeData


@dataclass
class AnalysisEntry:
    resume_id: str
    jd_text: str
    skill_matches: list[PhraseMatch]
    rewrite_suggestions: list[RewriteSuggestion]


def new_id() -> str:
    return secrets.token_hex(8)
