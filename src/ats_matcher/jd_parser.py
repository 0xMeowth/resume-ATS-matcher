from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests
import spacy
from bs4 import BeautifulSoup

from ats_matcher.nlp.esco import build_entity_ruler_patterns, load_esco_skill_phrases
from ats_matcher.nlp.skill_config import load_skill_extraction_config
from ats_matcher.utils import dedupe_preserve_order, normalize_text

TOOLISH_TOKEN_REGEX = re.compile(
    r"^(c\+\+|c#|\.net|node\.js|react\.js|next\.js|[a-z0-9]+[+#./&-][a-z0-9+#./&-]*)$",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


class _DebugCapture(logging.Handler):
    """Captures structured debug log records emitted during skill extraction."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.events: List[Dict[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.events.append(json.loads(self.format(record)))
        except Exception:
            pass


class JDParser:
    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        selected_esco_version: str = "latest",
        esco_cache_dir: str = ".cache/ats_matcher/esco",
        esco_skill_phrases: Optional[List[str]] = None,
        skill_config_path: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.selected_esco_version = selected_esco_version
        self.esco_cache_dir = esco_cache_dir
        self._esco_skill_phrases = esco_skill_phrases
        self._nlp = None
        self._resolved_esco_version = None
        config = load_skill_extraction_config(skill_config_path)
        self.light_head = config.light_head
        self.domain_stoplist = config.domain_stoplist
        self.single_token_allowlist = config.single_token_allowlist
        self.discourse_markers = config.discourse_markers
        self._leading_discourse_marker_regex = self._compile_leading_discourse_regex(
            self.discourse_markers
        )

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

    def extract_skill_terms(self, jd_text: str, debug: bool = False) -> List[str]:
        components = self.extract_skill_components(jd_text, debug=debug)
        return components["combined_skills"]

    def extract_skill_components(
        self, jd_text: str, debug: bool = False
    ) -> Dict[str, Any]:
        """Extract skill candidates from ESCO entities and cleaned noun chunks.

        - ESCO entities come from a local EntityRuler loaded once at parser init.
        - Noun chunks are cleaned with light-head stripping to reduce generic terms.
        """
        capture: Optional[_DebugCapture] = None
        if debug:
            capture = _DebugCapture()
            capture.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(capture)
            logger.setLevel(logging.DEBUG)

        try:
            doc = self.nlp(jd_text)
            esco_skills = self._extract_esco_entities(doc)
            noun_chunk_skills = self._extract_clean_noun_chunks(doc)
            single_token_skills = self._extract_allowlisted_single_tokens(doc)
            combined = esco_skills + noun_chunk_skills + single_token_skills
            combined = dedupe_preserve_order(combined)
            combined = self._suppress_substrings(combined, source="combined")
        finally:
            if capture is not None:
                logger.removeHandler(capture)

        result: Dict[str, Any] = {
            "esco_skills": esco_skills,
            "noun_chunk_skills": noun_chunk_skills,
            "single_token_skills": single_token_skills,
            "combined_skills": combined,
        }
        if capture is not None:
            result["debug_events"] = capture.events
        return result

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
            if "\n" in doc.text[ent.start_char : ent.end_char]:
                logger.debug(json.dumps({"phase": "extraction", "source": "esco_entity", "candidate": ent.text, "action": "dropped", "reason": "crosses_newline"}))
                continue
            candidate = self._normalize_candidate(ent.text)
            if not candidate:
                continue
            rejection_reason = self._candidate_rejection_reason(candidate)
            if rejection_reason:
                logger.debug(json.dumps({"phase": "extraction", "source": "esco_entity", "candidate": candidate, "action": "dropped", "reason": rejection_reason}))
                continue
            phrases.append(candidate)
            keep_reason = (
                "kept_allowlisted_short_token"
                if self._is_allowlisted_short_token(candidate)
                else "passed"
            )
            logger.debug(json.dumps({"phase": "extraction", "source": "esco_entity", "candidate": candidate, "action": "kept", "reason": keep_reason}))
        phrases = dedupe_preserve_order(phrases)
        return self._suppress_substrings(phrases, source="esco_entity")

    def _extract_clean_noun_chunks(self, doc) -> List[str]:
        phrases: List[str] = []
        for chunk in doc.noun_chunks:
            for candidate in self._clean_noun_chunk_candidates(chunk):
                if not candidate:
                    continue
                rejection_reason = self._candidate_rejection_reason(candidate)
                if rejection_reason:
                    logger.debug(json.dumps({"phase": "extraction", "source": "noun_chunk", "candidate": candidate, "action": "dropped", "reason": rejection_reason}))
                    continue
                phrases.append(candidate)
                keep_reason = (
                    "kept_allowlisted_short_token"
                    if self._is_allowlisted_short_token(candidate)
                    else "passed"
                )
                logger.debug(json.dumps({"phase": "extraction", "source": "noun_chunk", "candidate": candidate, "action": "kept", "reason": keep_reason}))
        phrases = dedupe_preserve_order(phrases)
        return self._suppress_substrings(phrases, source="noun_chunk")

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
            if normalize_text(candidate) in self.domain_stoplist:
                logger.debug(json.dumps({"phase": "extraction", "source": "single_token", "candidate": candidate, "action": "dropped", "reason": "domain_stoplist"}))
                continue
            if self._allow_single_token(candidate):
                phrases.append(candidate)
                logger.debug(json.dumps({"phase": "extraction", "source": "single_token", "candidate": candidate, "action": "kept", "reason": "allowlisted_or_toolish"}))
            else:
                logger.debug(json.dumps({"phase": "extraction", "source": "single_token", "candidate": candidate, "action": "dropped", "reason": "single_token_not_allowlisted"}))
        return dedupe_preserve_order(phrases)

    def _clean_noun_chunk_candidates(self, chunk) -> List[str]:
        """Return cleaned noun chunk with light-head stripping.

        A chunk like "enterprise performance area" has root/head "area".
        If the head lemma is generic (light-head), we drop the head token and keep
        informative modifiers only, e.g. "enterprise performance".

        Newline boundaries are treated as hard breaks to avoid cross-line artifacts
        like "AI Competency" from "AI\nCompetency".
        """
        tokens = [
            token
            for token in chunk
            if not token.is_punct and not token.is_space and not token.like_num
        ]
        if not tokens:
            return []

        candidates: List[str] = []
        for segment in self._split_tokens_on_hard_break(tokens):
            if not segment:
                continue
            candidate = self._clean_noun_chunk_segment(segment, chunk.root)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _clean_noun_chunk_segment(self, tokens: List, root) -> Optional[str]:
        root_in_segment = any(token.i == root.i for token in tokens)

        if root_in_segment and normalize_text(root.lemma_) in self.light_head:
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

    def _split_tokens_on_hard_break(self, tokens: List) -> List[List]:
        segments: List[List] = []
        current: List = []
        for idx, token in enumerate(tokens):
            current.append(token)
            next_token = tokens[idx + 1] if idx + 1 < len(tokens) else None
            if next_token is not None and self._contains_hard_break_between(
                token, next_token
            ):
                segments.append(current)
                current = []
        if current:
            segments.append(current)
        return segments

    def _contains_hard_break_between(self, left_token, right_token) -> bool:
        gap_text = left_token.doc.text[
            left_token.idx + len(left_token.text) : right_token.idx
        ]
        return "\n" in gap_text

    def _trim_determiners(self, tokens: List) -> List:
        while tokens and (tokens[0].pos_ == "DET" or tokens[0].is_stop):
            tokens = tokens[1:]
        while tokens and tokens[-1].is_punct:
            tokens = tokens[:-1]
        return tokens

    def _normalize_candidate(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip(" ,.;:()[]{}")
        text = self._strip_discourse_markers(text)
        return text

    def _candidate_rejection_reason(self, candidate: str) -> Optional[str]:
        normalized = normalize_text(candidate)
        if not normalized:
            return "empty_after_normalization"

        tokens = normalized.split()
        if len(tokens) == 1 and self._allow_single_token(candidate):
            return None

        if len(normalized) < 3:
            return "too_short"

        if normalized in self.domain_stoplist:
            return "domain_stoplist"
        if all(token in self.domain_stoplist for token in tokens):
            return "all_tokens_domain_stoplist"

        if len(tokens) < 2 and not self._allow_single_token(candidate):
            return "single_token_not_allowlisted"
        return None

    def _allow_single_token(self, candidate: str) -> bool:
        normalized = normalize_text(candidate)
        compact = normalized.replace(" ", "")
        if compact in self.single_token_allowlist:
            return True

        raw = candidate.strip()
        if TOOLISH_TOKEN_REGEX.match(raw):
            return True

        uppercase_raw = re.sub(r"[^A-Za-z0-9+#.&/-]", "", raw)
        if uppercase_raw.isupper() and 2 <= len(uppercase_raw) <= 8:
            return True
        return False

    def _is_allowlisted_short_token(self, candidate: str) -> bool:
        normalized = normalize_text(candidate)
        if len(normalized) >= 3:
            return False
        if len(normalized.split()) != 1:
            return False
        return self._allow_single_token(candidate)

    def _strip_discourse_markers(self, text: str) -> str:
        if not text:
            return text
        cleaned = text
        for _ in range(3):
            next_cleaned = self._leading_discourse_marker_regex.sub("", cleaned).strip(
                " ,.;:()[]{}"
            )
            if next_cleaned == cleaned:
                break
            cleaned = next_cleaned
        return cleaned

    def _compile_leading_discourse_regex(self, markers: List[str]) -> re.Pattern[str]:
        variants: List[str] = []
        for marker in markers:
            escaped = re.escape(marker)
            escaped = escaped.replace(r"\ ", r"\s+")
            variants.append(escaped)
        if not variants:
            return re.compile(r"^$")
        joined = "|".join(sorted(variants, key=len, reverse=True))
        return re.compile(
            rf"^(?:{joined})(?=\s|$|[,;:.-])[\s,;:.-]*",
            re.IGNORECASE,
        )

    def _suppress_substrings(
        self,
        phrases: List[str],
        source: str = "unknown",
    ) -> List[str]:
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
                    logger.debug(json.dumps({"phase": "dedupe", "source": source, "candidate": phrase, "action": "dropped", "reason": f"substring_of:{other}"}))
                    is_substring = True
                    break
            if not is_substring:
                kept.append(phrase)
        return kept
