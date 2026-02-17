from __future__ import annotations

from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def select_phrases_mmr(
    phrases: List[str],
    phrase_embeddings: np.ndarray,
    doc_embedding: np.ndarray,
    max_phrases: int,
    diversity: float = 0.3,
) -> List[int]:
    if not phrases:
        return []
    if phrase_embeddings.size == 0:
        return []

    max_phrases = max(1, min(max_phrases, len(phrases)))
    doc_embedding = doc_embedding.reshape(1, -1)
    relevance = np.dot(phrase_embeddings, doc_embedding.T).reshape(-1)
    similarity = np.dot(phrase_embeddings, phrase_embeddings.T)

    selected = [int(np.argmax(relevance))]
    candidates = set(range(len(phrases))) - set(selected)
    lambda_weight = 1.0 - diversity

    while len(selected) < max_phrases and candidates:
        best_idx = None
        best_score = -1e9
        for idx in candidates:
            redundancy = max(similarity[idx][j] for j in selected)
            score = lambda_weight * relevance[idx] - (1.0 - lambda_weight) * redundancy
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            break
        selected.append(best_idx)
        candidates.remove(best_idx)

    return selected


def rank_phrases_tfidf(
    phrases: List[str],
    document: str,
    max_phrases: int,
) -> List[int]:
    if not phrases:
        return []

    max_phrases = max(1, min(max_phrases, len(phrases)))
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    corpus = [document] + phrases
    matrix = vectorizer.fit_transform(corpus)
    doc_vec = matrix[0]
    phrase_vecs = matrix[1:]
    scores = (phrase_vecs @ doc_vec.T).toarray().reshape(-1)
    ranked = np.argsort(-scores)
    return [int(idx) for idx in ranked[:max_phrases]]
