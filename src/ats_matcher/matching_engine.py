from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from ats_matcher.models import PhraseMatch, ResumeData
from ats_matcher.utils import normalize_text


class MatchingEngine:
    def __init__(
        self,
        skill_strong_threshold: float = 0.7,
        skill_weak_threshold: float = 0.55,
        cross_encoder: Any = None,
        cross_encoder_threshold: float = 0.0,
    ) -> None:
        self.skill_strong_threshold = skill_strong_threshold
        self.skill_weak_threshold = skill_weak_threshold
        self.cross_encoder = cross_encoder
        self.cross_encoder_threshold = cross_encoder_threshold

    def match_skill_terms(
        self,
        phrases: List[str],
        resume: ResumeData,
        phrase_embeddings: np.ndarray,
        bullet_embeddings: np.ndarray,
        bullet_ids: List[str],
        matching_strategy: str = "embedding",
        rerank_top_k: int = 15,
    ) -> List[PhraseMatch]:
        matches: List[PhraseMatch] = []
        bullet_texts = {
            bullet_id: resume.bullet_index[bullet_id].text for bullet_id in bullet_ids
        }
        normalized_bullets = {
            bullet_id: normalize_text(text) for bullet_id, text in bullet_texts.items()
        }
        vectorizer, matrix = self._build_tfidf(bullet_texts.values())

        for idx, phrase in enumerate(phrases):
            normalized_phrase = normalize_text(phrase)
            exact_bullet_id = None
            for bullet_id, bullet_text in normalized_bullets.items():
                if self._contains_exact_phrase(normalized_phrase, bullet_text):
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
            candidate_indices = self._candidate_indices(
                phrase,
                matching_strategy,
                vectorizer,
                matrix,
                rerank_top_k,
            )

            best_score, best_bullet_id = self._best_semantic_match(
                phrase,
                phrase_vec,
                bullet_embeddings,
                bullet_ids,
                bullet_texts,
                candidate_indices,
            )
            evidence_text = bullet_texts[best_bullet_id] if best_bullet_id else None

            if best_score >= self.skill_strong_threshold:
                match_type = "semantic_strong"
            elif best_score >= self.skill_weak_threshold:
                match_type = "semantic_weak"
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

    def _candidate_indices(
        self,
        query: str,
        matching_strategy: str,
        vectorizer: Optional[TfidfVectorizer],
        matrix,
        rerank_top_k: int,
    ) -> Optional[List[int]]:
        if matching_strategy != "tfidf_rerank":
            return None
        if vectorizer is None or matrix is None:
            return None
        if rerank_top_k <= 0:
            return None
        return self._tfidf_top_indices(query, vectorizer, matrix, rerank_top_k)

    def _best_semantic_match(
        self,
        phrase: str,
        query_vec: np.ndarray,
        bullet_embeddings: np.ndarray,
        bullet_ids: List[str],
        bullet_texts: dict,
        candidate_indices: Optional[List[int]],
    ) -> Tuple[float, Optional[str]]:
        if candidate_indices is None:
            sims = np.dot(bullet_embeddings, query_vec.T).reshape(-1)
            top_indices = list(range(len(bullet_ids)))
        else:
            if not candidate_indices:
                return 0.0, None
            subset_embeddings = bullet_embeddings[candidate_indices]
            sims = np.dot(subset_embeddings, query_vec.T).reshape(-1)
            top_indices = candidate_indices

        if self.cross_encoder is not None:
            pairs = [(phrase, bullet_texts[bullet_ids[i]]) for i in top_indices]
            ce_scores = self.cross_encoder.predict(pairs)
            best_local = int(np.argmax(ce_scores))
            best_score = float(ce_scores[best_local])
            # Normalize cross-encoder score via sigmoid so it's in (0, 1)
            best_score = float(1 / (1 + np.exp(-best_score)))
            best_idx = top_indices[best_local]
        else:
            best_local = int(np.argmax(sims))
            best_score = float(sims[best_local])
            best_idx = top_indices[best_local]

        return best_score, bullet_ids[best_idx]

    def _build_tfidf(
        self, texts: List[str]
    ) -> Tuple[Optional[TfidfVectorizer], Optional[np.ndarray]]:
        text_list = list(texts)
        if not text_list:
            return None, None
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(text_list)
        return vectorizer, matrix

    def _tfidf_top_indices(
        self,
        query: str,
        vectorizer: TfidfVectorizer,
        matrix,
        top_k: int,
    ) -> List[int]:
        query_vec = vectorizer.transform([query])
        scores = (matrix @ query_vec.T).toarray().reshape(-1)
        top_k = min(top_k, len(scores))
        ranked = np.argsort(-scores)[:top_k]
        return [int(idx) for idx in ranked]

    def _contains_exact_phrase(
        self, normalized_phrase: str, normalized_bullet: str
    ) -> bool:
        if not normalized_phrase or not normalized_bullet:
            return False
        pattern = rf"(?<![a-z0-9+/#-]){re.escape(normalized_phrase)}(?![a-z0-9+/#-])"
        return re.search(pattern, normalized_bullet) is not None
