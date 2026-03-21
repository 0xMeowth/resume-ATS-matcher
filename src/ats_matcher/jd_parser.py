from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import yaml

import requests
import spacy
from bs4 import BeautifulSoup

from pathlib import Path

from ats_matcher.nlp.esco import build_entity_ruler_patterns, load_esco_skill_phrases
from ats_matcher.nlp.skill_config import load_skill_extraction_config
from ats_matcher.utils import dedupe_preserve_order, normalize_text

TOOLISH_TOKEN_REGEX = re.compile(
    r"^(c\+\+|c#|\.net|node\.js|react\.js|next\.js|[a-z0-9]+[+#./&-][a-z0-9+#./&-]*)$",
    re.IGNORECASE,
)

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Common slash-compounds to keep as single tokens
_SLASH_COMPOUNDS = [
    "CI/CD", "AI/ML", "ETL/ELT", "SaaS/PaaS", "IaaS/PaaS",
    "TCP/IP", "I/O", "OT/IoT", "B2B/B2C", "UI/UX",
]

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
        mcf_skills_path: str = "config/mcf_skills.json",
        custom_skills_path: str = "config/custom_skills.yaml",
    ) -> None:
        self.model_name = model_name
        self.selected_esco_version = selected_esco_version
        self.esco_cache_dir = esco_cache_dir
        self._esco_skill_phrases = esco_skill_phrases
        self._mcf_skills_path = mcf_skills_path
        self._custom_skills_path = custom_skills_path
        self._nlp = None
        self._resolved_esco_version = None
        config = load_skill_extraction_config(skill_config_path)
        self.light_head = config.light_head
        self.domain_stoplist = config.domain_stoplist
        self.single_token_allowlist = config.single_token_allowlist
        self.discourse_markers = config.discourse_markers
        self.vague_outcome_nouns = config.vague_outcome_nouns
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
            self._install_slash_compound_tokenizer_rules()
            self._install_esco_entity_ruler()
            self._install_mcf_entity_ruler()
            self._install_custom_entity_ruler()
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
            jd_text = self._preprocess_text(jd_text)
            self._current_jd_text = jd_text
            doc = self.nlp(jd_text)
            esco_skills = self._extract_esco_entities(doc)
            noun_chunk_skills = self._extract_clean_noun_chunks(doc)
            single_token_skills = self._extract_allowlisted_single_tokens(doc)
            combined = esco_skills + noun_chunk_skills + single_token_skills
            combined = dedupe_preserve_order(combined)
            combined = self._lemma_dedup(combined)
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

    def _preprocess_text(self, text: str) -> str:
        """Clean raw JD text before spaCy processing.

        Strips HTML tags, URLs, and email addresses. Extracts company name
        from ``Company:`` header (added by fetch_jds.py) into per-call
        stoplist. Preserves newlines for hard-break detection.
        """
        text = _HTML_TAG_RE.sub(" ", text)
        text = _URL_RE.sub("", text)
        text = _EMAIL_RE.sub("", text)
        self._extract_company_stopwords(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_company_stopwords(self, text: str) -> None:
        """Parse ``Company: <name>`` header and add tokens to per-call stoplist."""
        self._company_stopwords: set[str] = set()
        match = re.search(r"^Company:\s*(.+)$", text, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            tokens = re.findall(r"[a-z]+", name.lower())
            # Filter out common company suffixes already in domain_stoplist
            self._company_stopwords = {
                t for t in tokens if len(t) > 2 and t not in self.domain_stoplist
            }

    def _install_slash_compound_tokenizer_rules(self) -> None:
        """Add special-case tokenizer rules so slash-compounds stay as one token."""
        for compound in _SLASH_COMPOUNDS:
            for form in (compound, compound.lower(), compound.upper()):
                self._nlp.tokenizer.add_special_case(
                    form, [{"ORTH": form}]
                )

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

    def _install_mcf_entity_ruler(self) -> None:
        """Load MCF skill dictionary and add as entity ruler patterns."""
        mcf_path = Path(self._mcf_skills_path)
        if not mcf_path.exists():
            return
        if "mcf_skill_ruler" in self._nlp.pipe_names:
            return

        phrases = json.loads(mcf_path.read_text(encoding="utf-8"))
        if not phrases:
            return

        ruler = self._nlp.add_pipe(
            "entity_ruler",
            name="mcf_skill_ruler",
            config={"phrase_matcher_attr": "LOWER", "overwrite_ents": False},
            after="esco_skill_ruler" if "esco_skill_ruler" in self._nlp.pipe_names else None,
        )
        ruler.add_patterns(build_entity_ruler_patterns(phrases, label="MCF_SKILL"))
        logger.info("Loaded %d MCF skill patterns", len(phrases))

    def _install_custom_entity_ruler(self) -> None:
        """Load custom skill dictionary and add as entity ruler patterns."""
        custom_path = Path(self._custom_skills_path)
        if not custom_path.exists():
            return
        if "custom_skill_ruler" in self._nlp.pipe_names:
            return

        data = yaml.safe_load(custom_path.read_text(encoding="utf-8"))
        phrases = data.get("skills", []) if data else []
        if not phrases:
            return

        last_ruler = (
            "mcf_skill_ruler" if "mcf_skill_ruler" in self._nlp.pipe_names
            else "esco_skill_ruler" if "esco_skill_ruler" in self._nlp.pipe_names
            else None
        )
        ruler = self._nlp.add_pipe(
            "entity_ruler",
            name="custom_skill_ruler",
            config={"phrase_matcher_attr": "LOWER", "overwrite_ents": False},
            after=last_ruler,
        )
        ruler.add_patterns(build_entity_ruler_patterns(phrases, label="CUSTOM_SKILL"))
        logger.info("Loaded %d custom skill patterns", len(phrases))

    _SKILL_ENTITY_LABELS = {"ESCO_SKILL", "MCF_SKILL", "CUSTOM_SKILL"}

    def _extract_esco_entities(self, doc) -> List[str]:
        phrases: List[str] = []
        for ent in doc.ents:
            if ent.label_ not in self._SKILL_ENTITY_LABELS:
                continue
            if "\n" in doc.text[ent.start_char : ent.end_char]:
                logger.debug(json.dumps({"phase": "extraction", "source": "esco_entity", "candidate": ent.text, "action": "dropped", "reason": "crosses_newline"}))
                continue
            candidate = self._normalize_candidate(ent.text)
            if not candidate:
                continue
            for part in self._split_or_alternatives(candidate):
                rejection_reason = self._candidate_rejection_reason(part)
                if rejection_reason:
                    logger.debug(json.dumps({"phase": "extraction", "source": "esco_entity", "candidate": part, "action": "dropped", "reason": rejection_reason}))
                    continue
                phrases.append(part)
                keep_reason = (
                    "kept_allowlisted_short_token"
                    if self._is_allowlisted_short_token(part)
                    else "passed"
                )
                logger.debug(json.dumps({"phase": "extraction", "source": "esco_entity", "candidate": part, "action": "kept", "reason": keep_reason}))
        phrases = dedupe_preserve_order(phrases)
        return self._suppress_substrings(phrases, source="esco_entity")

    def _extract_clean_noun_chunks(self, doc) -> List[str]:
        phrases: List[str] = []
        for chunk in doc.noun_chunks:
            for candidate in self._clean_noun_chunk_candidates(chunk):
                if not candidate:
                    continue
                for part in self._split_or_alternatives(candidate):
                    rejection_reason = self._candidate_rejection_reason(part)
                    if rejection_reason:
                        logger.debug(json.dumps({"phase": "extraction", "source": "noun_chunk", "candidate": part, "action": "dropped", "reason": rejection_reason}))
                        continue
                    phrases.append(part)
                    keep_reason = (
                        "kept_allowlisted_short_token"
                        if self._is_allowlisted_short_token(part)
                        else "passed"
                    )
                    logger.debug(json.dumps({"phase": "extraction", "source": "noun_chunk", "candidate": part, "action": "kept", "reason": keep_reason}))
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
                logger.debug(json.dumps({"phase": "extraction", "source": "single_token", "candidate": candidate, "action": "dropped", "reason": "generic_nouns"}))
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
        if not candidate:
            return None
        if len(candidate.split()) > 6:
            return None
        return candidate

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

    def _split_or_alternatives(self, phrase: str) -> List[str]:
        """Split 'Kafka OR Redis clusters' → ['Kafka', 'Redis clusters'].
        Runs after _normalize_candidate; each part re-enters validation."""
        if not re.search(r'\bOR\b', phrase, re.IGNORECASE):
            return [phrase]
        parts = re.split(r'\s+OR\s+', phrase, flags=re.IGNORECASE)
        return [p.strip() for p in parts if p.strip()]

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
            return "generic_nouns"
        if all(token in self.domain_stoplist for token in tokens):
            return "all_tokens_generic_nouns"

        company_sw = getattr(self, "_company_stopwords", set())
        if company_sw and all(token in company_sw or token in self.domain_stoplist for token in tokens):
            return "company_name"

        if len(tokens) > 1 and tokens[-1] in self.vague_outcome_nouns:
            has_toolish = any(
                TOOLISH_TOKEN_REGEX.match(tok)
                for tok in candidate.split()
            )
            if not has_toolish:
                return "vague_head_noun"

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

        # Allow 3-char mixed-case abbreviations like VaR, DoS, PoW (first and last uppercase)
        if re.match(r'^[A-Z][^A-Z][A-Z]$', raw.strip()):
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

    def _is_prefix_acronym_of_longer(
        self, short_norm: str, all_normalized: List[str]
    ) -> bool:
        """True if short_norm is an all-caps 2–5 char token AND
        any longer candidate in all_normalized starts with 'short_norm '."""
        compact = short_norm.replace(" ", "")
        if not (compact.isupper() and 2 <= len(compact) <= 5):
            return False
        prefix = short_norm + " "
        return any(
            other != short_norm and other.startswith(prefix)
            for other in all_normalized
        )

    def _lemma_dedup(self, phrases: List[str]) -> List[str]:
        """Collapse near-duplicate phrases that differ only in inflection.

        Uses spaCy lemmatization per word to build a canonical key for grouping.
        Keeps the first surface form seen. Displayed output is never lemmatized.
        """
        seen_keys: dict[str, str] = {}  # lemma_key -> first surface form
        result: List[str] = []
        for phrase in phrases:
            doc = self.nlp(phrase)
            key = " ".join(token.lemma_.lower() for token in doc)
            if key not in seen_keys:
                seen_keys[key] = phrase
                result.append(phrase)
            else:
                logger.debug(json.dumps({"phase": "dedupe", "source": "lemma_dedup", "candidate": phrase, "action": "dropped", "reason": f"lemma_duplicate_of:{seen_keys[key]}"}))
        return result

    def _suppress_substrings(
        self,
        phrases: List[str],
        source: str = "unknown",
        jd_text: Optional[str] = None,
    ) -> List[str]:
        kept: List[str] = []
        normalized = [normalize_text(phrase) for phrase in phrases]
        if jd_text is None:
            jd_text = getattr(self, "_current_jd_text", None)
        jd_lower = jd_text.lower() if jd_text else None

        for idx, phrase in enumerate(phrases):
            short_norm = normalized[idx]
            if not short_norm:
                continue
            if len(short_norm.split()) == 1 and self._allow_single_token(phrase):
                if not self._is_prefix_acronym_of_longer(short_norm, normalized):
                    kept.append(phrase)
                    continue
                # fall through — subject to normal subsumption
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
                    # C1: keep shorter phrase if it appears independently in the JD
                    if jd_lower and self._phrase_appears_independently(
                        short_norm, long_norm, jd_lower
                    ):
                        logger.debug(json.dumps({"phase": "dedupe", "source": source, "candidate": phrase, "action": "kept", "reason": f"independent_of:{other}"}))
                        break
                    logger.debug(json.dumps({"phase": "dedupe", "source": source, "candidate": phrase, "action": "dropped", "reason": f"substring_of:{other}"}))
                    is_substring = True
                    break
            if not is_substring:
                kept.append(phrase)
        return kept

    @staticmethod
    def _phrase_appears_independently(
        short_norm: str, long_norm: str, jd_lower: str
    ) -> bool:
        """Return True if the short phrase appears in the text outside the long phrase."""
        stripped = re.sub(rf"\b{re.escape(long_norm)}\b", "", jd_lower)
        return bool(re.search(rf"\b{re.escape(short_norm)}\b", stripped))
