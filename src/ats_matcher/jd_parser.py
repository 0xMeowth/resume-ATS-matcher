from __future__ import annotations

import re
from typing import Dict, List, Optional

import requests
import spacy
from bs4 import BeautifulSoup

from ats_matcher.nlp.esco import build_entity_ruler_patterns, load_esco_skill_phrases
from ats_matcher.utils import dedupe_preserve_order, normalize_text


LIGHT_HEAD = {
    "area",
    "field",
    "domain",
    "space",
    "scope",
    "aspect",
    "environment",
    "function",
    "capacity",
    "capability",
    "knowledge",
    "experience",
    "skills",
    "skill",
    "background",
    "exposure",
}

DOMAIN_STOPLIST = {
    "ability",
    "area",
    "background",
    "domain",
    "environment",
    "experience",
    "exposure",
    "function",
    "knowledge",
    "minimum",
    "relevant",
    "scope",
    "skill",
    "skills",
    "stakeholders",
    "team",
    "working",
    "years",
    "year",
}

SINGLE_TOKEN_ALLOWLIST = {
    "ai",
    "api",
    "aws",
    "bi",
    "ci",
    "crm",
    "etl",
    "excel",
    "fpa",
    "fp&a",
    "gcp",
    "git",
    "java",
    "jira",
    "linux",
    "nosql",
    "ocr",
    "powerbi",
    "sap",
    "scala",
    "snowflake",
    "spark",
    "sql",
    "tableau",
}

TOOLISH_TOKEN_REGEX = re.compile(
    r"^(c\+\+|c#|\.net|node\.js|react\.js|next\.js|[a-z0-9]+[+#./&-][a-z0-9+#./&-]*)$",
    re.IGNORECASE,
)


class JDParser:
    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        selected_esco_version: str = "latest",
        esco_cache_dir: str = ".cache/ats_matcher/esco",
        esco_skill_phrases: Optional[List[str]] = None,
    ) -> None:
        self.model_name = model_name
        self.selected_esco_version = selected_esco_version
        self.esco_cache_dir = esco_cache_dir
        self._esco_skill_phrases = esco_skill_phrases
        self._nlp = None
        self._resolved_esco_version = None

    @property
    def nlp(self):
        if self._nlp is None:
            self._nlp = spacy.load(self.model_name, disable=["ner", "textcat"])
            if (
                "sentencizer" not in self._nlp.pipe_names
                and "parser" not in self._nlp.pipe_names
            ):
                self._nlp.add_pipe("sentencizer")
            self._install_esco_entity_ruler()
        return self._nlp

    @property
    def resolved_esco_version(self) -> Optional[str]:
        return self._resolved_esco_version

    def load_text(self, jd_text: Optional[str], jd_url: Optional[str]) -> str:
        if jd_url:
            return self._fetch_url(jd_url)
        return jd_text or ""

    def extract_skill_terms(self, jd_text: str) -> List[str]:
        components = self.extract_skill_components(jd_text)
        combined = (
            components["esco_skills"]
            + components["noun_chunk_skills"]
            + components["single_token_skills"]
        )
        combined = dedupe_preserve_order(combined)
        combined = self._suppress_substrings(combined)
        return combined

    def extract_skill_components(self, jd_text: str) -> Dict[str, List[str]]:
        """Extract skill candidates from ESCO entities and cleaned noun chunks.

        - ESCO entities come from a local EntityRuler loaded once at parser init.
        - Noun chunks are cleaned with light-head stripping to reduce generic terms.
        """
        doc = self.nlp(jd_text)
        esco_skills = self._extract_esco_entities(doc)
        noun_chunk_skills = self._extract_clean_noun_chunks(doc)
        single_token_skills = self._extract_allowlisted_single_tokens(doc)
        return {
            "esco_skills": esco_skills,
            "noun_chunk_skills": noun_chunk_skills,
            "single_token_skills": single_token_skills,
        }

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

    def _install_esco_entity_ruler(self) -> None:
        phrases = self._esco_skill_phrases
        if phrases is None:
            version, phrases = load_esco_skill_phrases(
                selected_version=self.selected_esco_version,
                cache_dir=self.esco_cache_dir,
            )
            self._resolved_esco_version = version
            self._esco_skill_phrases = phrases
        else:
            self._resolved_esco_version = self.selected_esco_version

        if not phrases:
            return
        if "esco_skill_ruler" in self._nlp.pipe_names:
            return

        ruler = self._nlp.add_pipe(
            "entity_ruler",
            name="esco_skill_ruler",
            config={"phrase_matcher_attr": "LOWER", "overwrite_ents": False},
            first=True,
        )
        ruler.add_patterns(build_entity_ruler_patterns(phrases))

    def _extract_esco_entities(self, doc) -> List[str]:
        phrases: List[str] = []
        for ent in doc.ents:
            if ent.label_ != "ESCO_SKILL":
                continue
            candidate = self._normalize_candidate(ent.text)
            if not candidate:
                continue
            if self._reject_candidate(candidate):
                continue
            phrases.append(candidate)
        phrases = dedupe_preserve_order(phrases)
        return self._suppress_substrings(phrases)

    def _extract_clean_noun_chunks(self, doc) -> List[str]:
        phrases: List[str] = []
        for chunk in doc.noun_chunks:
            candidate = self._clean_noun_chunk(chunk)
            if not candidate:
                continue
            if self._reject_candidate(candidate):
                continue
            phrases.append(candidate)
        phrases = dedupe_preserve_order(phrases)
        return self._suppress_substrings(phrases)

    def _extract_allowlisted_single_tokens(self, doc) -> List[str]:
        phrases: List[str] = []
        for token in doc:
            if token.is_punct or token.is_space or token.like_num:
                continue
            if token.is_stop:
                continue
            candidate = self._normalize_candidate(token.text)
            if not candidate:
                continue
            if normalize_text(candidate) in DOMAIN_STOPLIST:
                continue
            if self._allow_single_token(candidate):
                phrases.append(candidate)
        return dedupe_preserve_order(phrases)

    def _clean_noun_chunk(self, chunk) -> Optional[str]:
        """Return cleaned noun chunk with light-head stripping.

        A chunk like "enterprise performance area" has root/head "area".
        If the head lemma is generic (light-head), we drop the head token and keep
        informative modifiers only, e.g. "enterprise performance".
        """
        tokens = [token for token in chunk if not token.is_punct and not token.is_space]
        if not tokens:
            return None

        root = chunk.root
        if normalize_text(root.lemma_) in LIGHT_HEAD:
            tokens = [
                token
                for token in tokens
                if token.i != root.i and not token.is_stop and token.pos_ != "DET"
            ]
        else:
            tokens = self._trim_determiners(tokens)

        if not tokens:
            return None

        surface = " ".join(token.text for token in tokens)
        candidate = self._normalize_candidate(surface)
        return candidate or None

    def _trim_determiners(self, tokens: List) -> List:
        while tokens and (tokens[0].pos_ == "DET" or tokens[0].is_stop):
            tokens = tokens[1:]
        while tokens and tokens[-1].is_punct:
            tokens = tokens[:-1]
        return tokens

    def _normalize_candidate(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip(" ,.;:()[]{}")
        return text

    def _reject_candidate(self, candidate: str) -> bool:
        normalized = normalize_text(candidate)
        if not normalized:
            return True
        if len(normalized) < 3:
            return True

        tokens = normalized.split()
        if normalized in DOMAIN_STOPLIST:
            return True
        if all(token in DOMAIN_STOPLIST for token in tokens):
            return True

        if len(tokens) < 2 and not self._allow_single_token(candidate):
            return True
        return False

    def _allow_single_token(self, candidate: str) -> bool:
        normalized = normalize_text(candidate)
        compact = normalized.replace(" ", "")
        if compact in SINGLE_TOKEN_ALLOWLIST:
            return True

        raw = candidate.strip()
        if TOOLISH_TOKEN_REGEX.match(raw):
            return True

        uppercase_raw = re.sub(r"[^A-Za-z0-9+#.&/-]", "", raw)
        if uppercase_raw.isupper() and 2 <= len(uppercase_raw) <= 8:
            return True
        return False

    def _suppress_substrings(self, phrases: List[str]) -> List[str]:
        kept: List[str] = []
        normalized = [normalize_text(phrase) for phrase in phrases]

        for idx, phrase in enumerate(phrases):
            short_norm = normalized[idx]
            if not short_norm:
                continue
            if len(short_norm.split()) == 1 and self._allow_single_token(phrase):
                kept.append(phrase)
                continue
            is_substring = False
            for jdx, other in enumerate(phrases):
                if idx == jdx:
                    continue
                long_norm = normalized[jdx]
                if not long_norm or short_norm == long_norm:
                    continue
                if len(long_norm.split()) > 8:
                    continue
                if re.search(rf"\b{re.escape(short_norm)}\b", long_norm):
                    is_substring = True
                    break
            if not is_substring:
                kept.append(phrase)
        return kept
