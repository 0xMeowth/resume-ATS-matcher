from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from ats_matcher.utils import normalize_text

ESCO_API_BASE_URL = "https://ec.europa.eu/esco/api"
ESCO_DOWNLOAD_PAGE_URL = "https://esco.ec.europa.eu/en/use-esco/download"
ESCO_SKILL_SCHEME_URI = "http://data.europa.eu/esco/concept-scheme/skills"
ESCO_ENTITY_LABEL = "ESCO_SKILL"
DEFAULT_CACHE_DIR = ".cache/ats_matcher/esco"


def resolve_latest_esco_version(timeout: int = 20) -> str:
    """Resolve latest ESCO dataset version from the official download page."""
    response = requests.get(ESCO_DOWNLOAD_PAGE_URL, timeout=timeout)
    response.raise_for_status()
    match = re.search(r"Current version:\s*ESCO\s*(v\d+\.\d+\.\d+)", response.text)
    if not match:
        return "latest"
    return match.group(1)


def load_esco_skill_phrases(
    selected_version: str = "latest",
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    include_alt_labels: bool = True,
    max_tokens: int = 10,
    timeout: int = 20,
) -> tuple[str, list[str]]:
    """Load normalized ESCO skill phrases with local caching.

    The function resolves `latest` to a concrete version, reads from cache when
    available, and only calls ESCO Web Services when cache is missing.
    """
    try:
        resolved_version = (
            resolve_latest_esco_version(timeout=timeout)
            if selected_version == "latest"
            else selected_version
        )
    except requests.RequestException:
        resolved_version = (
            "latest" if selected_version == "latest" else selected_version
        )
    cache_path = _cache_file_path(cache_dir=cache_dir, version=resolved_version)
    cached = _read_cache(cache_path)
    if cached is not None:
        return resolved_version, cached

    try:
        phrases = _download_esco_skill_phrases(
            selected_version=resolved_version,
            include_alt_labels=include_alt_labels,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            "Failed to fetch ESCO skills from official API. "
            "Prebuild cache or check network connectivity."
        ) from exc
    _write_cache(
        cache_path=cache_path,
        selected_version=resolved_version,
        include_alt_labels=include_alt_labels,
        max_tokens=max_tokens,
        phrases=phrases,
    )
    return resolved_version, phrases


def build_entity_ruler_patterns(
    skill_phrases: list[str],
    label: str = ESCO_ENTITY_LABEL,
) -> list[dict[str, str]]:
    """Build spaCy EntityRuler phrase patterns from ESCO skill phrases."""
    return [{"label": label, "pattern": phrase} for phrase in skill_phrases]


def _download_esco_skill_phrases(
    selected_version: str,
    include_alt_labels: bool,
    max_tokens: int,
    timeout: int,
) -> list[str]:
    offset = 0
    limit = 300
    total = None
    raw_phrases: list[str] = []

    while total is None or offset < total:
        payload = _fetch_skill_page(
            selected_version=selected_version,
            offset=offset,
            limit=limit,
            timeout=timeout,
        )
        concepts = payload.get("_embedded", {})
        raw_phrases.extend(
            _extract_phrases_from_embedded(
                concepts=concepts,
                include_alt_labels=include_alt_labels,
            )
        )

        total = int(payload.get("total", 0))
        if total <= 0:
            break
        offset += limit

    return _normalize_and_filter_phrases(raw_phrases, max_tokens=max_tokens)


def _fetch_skill_page(
    selected_version: str,
    offset: int,
    limit: int,
    timeout: int,
) -> dict[str, Any]:
    response = requests.get(
        f"{ESCO_API_BASE_URL}/resource/skill",
        params={
            "isInScheme": ESCO_SKILL_SCHEME_URI,
            "language": "en",
            "selectedVersion": selected_version,
            "offset": offset,
            "limit": limit,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _extract_phrases_from_embedded(
    concepts: dict[str, Any], include_alt_labels: bool
) -> list[str]:
    phrases: list[str] = []
    for _, concept in concepts.items():
        preferred = _extract_english_preferred_label(concept)
        if preferred:
            phrases.append(preferred)

        if include_alt_labels:
            alt_labels = concept.get("alternativeLabel", {})
            if isinstance(alt_labels, dict):
                english_alts = alt_labels.get("en", [])
                if isinstance(english_alts, list):
                    for label in english_alts:
                        if isinstance(label, str) and label.strip():
                            phrases.append(label.strip())
    return phrases


def _extract_english_preferred_label(concept: dict[str, Any]) -> str | None:
    preferred = concept.get("preferredLabel", {})
    if not isinstance(preferred, dict):
        return None
    for key in ("en", "en-us"):
        value = preferred.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    title = concept.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _normalize_and_filter_phrases(raw_phrases: list[str], max_tokens: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in raw_phrases:
        normalized = _normalize_surface_phrase(phrase)
        if not normalized:
            continue
        if len(normalized) < 2:
            continue
        token_count = len(normalized.split())
        if token_count > max_tokens:
            continue

        normalized_for_key = normalize_text(normalized)
        if not normalized_for_key:
            continue
        if normalized_for_key in {"management", "skills", "skill", "knowledge"}:
            continue
        if normalized_for_key in seen:
            continue
        seen.add(normalized_for_key)
        deduped.append(normalized)
    return deduped


def _normalize_surface_phrase(phrase: str) -> str:
    phrase = re.sub(r"\s+", " ", phrase).strip()
    return phrase


def _cache_file_path(cache_dir: str | Path, version: str) -> Path:
    target_dir = Path(cache_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_version = re.sub(r"[^a-zA-Z0-9._-]", "_", version)
    return target_dir / f"skills_{safe_version}.json"


def _read_cache(cache_path: Path) -> list[str] | None:
    if not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    phrases = payload.get("phrases", [])
    if not isinstance(phrases, list):
        return None
    result = [item for item in phrases if isinstance(item, str) and item.strip()]
    return result if result else None


def _write_cache(
    cache_path: Path,
    selected_version: str,
    include_alt_labels: bool,
    max_tokens: int,
    phrases: list[str],
) -> None:
    payload = {
        "selected_version": selected_version,
        "include_alt_labels": include_alt_labels,
        "max_tokens": max_tokens,
        "created_at": datetime.now(UTC).isoformat(),
        "source": "ESCO Web Services API",
        "phrases": phrases,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
