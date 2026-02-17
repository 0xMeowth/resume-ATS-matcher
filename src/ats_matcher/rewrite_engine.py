from __future__ import annotations

from typing import List

from ats_matcher.models import PhraseMatch, ResumeData, RewriteSuggestion


class RewriteEngine:
    def __init__(self) -> None:
        pass

    def generate(
        self, matches: List[PhraseMatch], resume: ResumeData
    ) -> List[RewriteSuggestion]:
        suggestions: List[RewriteSuggestion] = []
        for match in matches:
            if match.match_type == "exact":
                continue
            if not match.evidence_bullet_id:
                continue
            bullet = resume.bullet_index.get(match.evidence_bullet_id)
            if not bullet:
                continue
            hint = f"Add keyword: {match.phrase}"
            suggestions.append(
                RewriteSuggestion(
                    bullet_id=bullet.bullet_id,
                    phrase=match.phrase,
                    original_text=bullet.text,
                    suggestion_text=hint,
                )
            )
        return suggestions
