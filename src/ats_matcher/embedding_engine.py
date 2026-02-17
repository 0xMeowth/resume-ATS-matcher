from __future__ import annotations

from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingEngine:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0))
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings)
