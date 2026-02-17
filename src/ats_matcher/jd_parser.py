from __future__ import annotations

import re
from typing import List, Optional

import requests
import spacy
from bs4 import BeautifulSoup

from ats_matcher.utils import dedupe_preserve_order, normalize_text


class JDParser:
    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self.model_name = model_name
        self._nlp = None

    @property
    def nlp(self):
        if self._nlp is None:
            self._nlp = spacy.load(self.model_name, disable=["ner", "textcat"])
        return self._nlp

    def load_text(self, jd_text: Optional[str], jd_url: Optional[str]) -> str:
        if jd_url:
            return self._fetch_url(jd_url)
        return jd_text or ""

    def extract_skill_terms(self, jd_text: str) -> List[str]:
        doc = self.nlp(jd_text)
        stopwords = self.nlp.Defaults.stop_words
        phrases: List[str] = []

        for chunk in doc.noun_chunks:
            phrase = normalize_text(chunk.text)
            if not phrase:
                continue
            if phrase in stopwords:
                continue
            if len(phrase) < 3:
                continue
            phrases.append(phrase)

        for token in doc:
            if token.is_stop or token.is_punct or token.like_num:
                continue
            if token.pos_ not in {"NOUN", "PROPN"}:
                continue
            phrase = normalize_text(token.text)
            if not phrase or phrase in stopwords:
                continue
            phrases.append(phrase)

        phrases = dedupe_preserve_order(phrases)
        return phrases

    def extract_requirements(self, jd_text: str) -> List[str]:
        doc = self.nlp(jd_text)
        requirements: List[str] = []
        for sent in doc.sents:
            sentence = re.sub(r"\s+", " ", sent.text).strip()
            if not sentence:
                continue
            token_count = len([t for t in sent if not t.is_punct])
            if token_count < 6:
                continue
            requirements.append(sentence)

        requirements = dedupe_preserve_order(requirements)
        return requirements

    def _fetch_url(self, url: str) -> str:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ")
        return re.sub(r"\s+", " ", text).strip()
