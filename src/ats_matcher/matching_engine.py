from __future__ import annotations

from typing import List, Tuple

import numpy as np

from ats_matcher.models import PhraseMatch, ResumeData
from ats_matcher.utils import normalize_text


class MatchingEngine:
    def __init__(self, semantic_threshold: float = 0.6) -> None:
        self.semantic_threshold = semantic_threshold

    def match_phrases(
        self,
        phrases: List[str],
        resume: ResumeData,
        phrase_embeddings: np.ndarray,
        bullet_embeddings: np.ndarray,
        bullet_ids: List[str],
    ) -> List[PhraseMatch]:
        matches: List[PhraseMatch] = []
        bullet_texts = {
            bullet_id: resume.bullet_index[bullet_id].text for bullet_id in bullet_ids
        }
        normalized_bullets = {
            bullet_id: normalize_text(text) for bullet_id, text in bullet_texts.items()
        }

        for idx, phrase in enumerate(phrases):
            normalized_phrase = normalize_text(phrase)
            exact_bullet_id = None
            for bullet_id, bullet_text in normalized_bullets.items():
                if normalized_phrase and normalized_phrase in bullet_text:
                    exact_bullet_id = bullet_id
                    break

            if exact_bullet_id:
                evidence_text = bullet_texts[exact_bullet_id]
                matches.append(
                    PhraseMatch(
                        phrase=phrase,
                        match_type="exact",
                        similarity=1.0,
                        evidence_bullet_id=exact_bullet_id,
                        evidence_text=evidence_text,
                    )
                )
                continue

            if bullet_embeddings.size == 0:
                matches.append(
                    PhraseMatch(
                        phrase=phrase,
                        match_type="missing",
                        similarity=0.0,
                        evidence_bullet_id=None,
                        evidence_text=None,
                    )
                )
                continue

            phrase_vec = phrase_embeddings[idx : idx + 1]
            sims = np.dot(bullet_embeddings, phrase_vec.T).reshape(-1)
            best_idx = int(np.argmax(sims))
            best_score = float(sims[best_idx])
            best_bullet_id = bullet_ids[best_idx]
            evidence_text = bullet_texts[best_bullet_id]

            if best_score >= self.semantic_threshold:
                match_type = "semantic"
            else:
                match_type = "missing"
                best_bullet_id = None
                evidence_text = None
                best_score = 0.0

            matches.append(
                PhraseMatch(
                    phrase=phrase,
                    match_type=match_type,
                    similarity=best_score,
                    evidence_bullet_id=best_bullet_id,
                    evidence_text=evidence_text,
                )
            )

        return matches
