from __future__ import annotations

import re
from typing import Iterable

from ats_matcher.models import ResumeData
from ats_matcher.utils import dedupe_preserve_order, normalize_text

BULLET_PREFIXES = ("•", "∙", "-", "–", "—", "*", "·")


def strip_leading_bullet_prefixes(text: str) -> str:
    cleaned = text
    while True:
        stripped = cleaned.lstrip()
        if not stripped:
            return ""
        if stripped.startswith(BULLET_PREFIXES):
            cleaned = stripped[1:]
            continue
        return stripped


def split_newline_terms(raw_text: str) -> list[str]:
    terms = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return dedupe_preserve_order(terms)


def extract_resume_text(resume: ResumeData, edits: dict[str, str]) -> str:
    fragments: list[str] = []
    for section in resume.sections:
        if section.title:
            fragments.append(section.title)
        for role in section.roles:
            if role.title:
                fragments.append(role.title)
            for bullet in role.bullets:
                bullet_text = edits.get(bullet.bullet_id, bullet.text)
                bullet_text = strip_leading_bullet_prefixes(bullet_text)
                if bullet_text:
                    fragments.append(bullet_text)
    return "\n".join(fragments)


def compute_coverage(
    terms: Iterable[str], resume_text: str
) -> tuple[list[str], list[str]]:
    normalized_resume = normalize_text(resume_text)
    covered: list[str] = []
    missing: list[str] = []

    canonical_terms = [term.strip() for term in terms if term and term.strip()]
    canonical_terms = dedupe_preserve_order(canonical_terms)

    for term in canonical_terms:
        if _is_term_covered(
            term=term, raw_resume_text=resume_text, normalized_resume=normalized_resume
        ):
            covered.append(term)
        else:
            missing.append(term)
    return covered, missing


def _is_term_covered(term: str, raw_resume_text: str, normalized_resume: str) -> bool:
    stripped_term = term.strip()
    if not stripped_term:
        return False

    if _is_toolish_term(stripped_term):
        escaped = re.escape(stripped_term)
        escaped = escaped.replace(r"\ ", r"\s+")
        pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
        return pattern.search(raw_resume_text) is not None

    normalized_term = normalize_text(stripped_term)
    if not normalized_term:
        return False
    escaped = re.escape(normalized_term).replace(r"\ ", r"\s+")
    pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return pattern.search(normalized_resume) is not None


def _is_toolish_term(term: str) -> bool:
    if term.startswith("."):
        return True
    return any(char in term for char in "+#./&-")
