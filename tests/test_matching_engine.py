from __future__ import annotations

import numpy as np

from ats_matcher.matching_engine import MatchingEngine
from ats_matcher.models import Bullet, ResumeData


def _resume_with_one_bullet(text: str) -> tuple[ResumeData, list[str]]:
    bullet_id = "b1"
    bullet = Bullet(
        bullet_id=bullet_id,
        text=text,
        paragraph_index=0,
        section_title="Experience",
        role_title="Role",
    )
    resume = ResumeData(sections=[], bullet_index={bullet_id: bullet})
    return resume, [bullet_id]


def test_ai_is_not_exact_matched_inside_chain() -> None:
    resume, bullet_ids = _resume_with_one_bullet(
        "Evaluated on-chain data and protocol mechanisms across DeFi"
    )
    matcher = MatchingEngine()

    matches = matcher.match_skill_terms(
        phrases=["AI"],
        resume=resume,
        phrase_embeddings=np.zeros((1, 4)),
        bullet_embeddings=np.zeros((1, 4)),
        bullet_ids=bullet_ids,
    )

    assert len(matches) == 1
    assert matches[0].match_type == "missing"
    assert matches[0].evidence_text is None


def test_sql_exact_match_uses_token_boundaries() -> None:
    resume, bullet_ids = _resume_with_one_bullet("Built SQL models for analytics")
    matcher = MatchingEngine()

    matches = matcher.match_skill_terms(
        phrases=["SQL"],
        resume=resume,
        phrase_embeddings=np.zeros((1, 4)),
        bullet_embeddings=np.zeros((1, 4)),
        bullet_ids=bullet_ids,
    )

    assert len(matches) == 1
    assert matches[0].match_type == "exact"
    assert matches[0].evidence_text == "Built SQL models for analytics"
