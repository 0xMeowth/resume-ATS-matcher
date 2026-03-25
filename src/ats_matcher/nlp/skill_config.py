from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SkillExtractionConfig:
    light_head: set[str]
    exclude_list: set[str]
    single_token_allowlist: set[str]
    discourse_markers: list[str]
    vague_tail_nouns: set[str]
    soft_skill_markers: list[str]
    academic_field_nouns: set[str]
    light_modifier: set[str]


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "skill_extraction.yaml"


def load_skill_extraction_config(
    config_path: str | Path | None = None,
) -> SkillExtractionConfig:
    path = Path(config_path) if config_path else default_config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Skill extraction config not found: {path}. "
            "Create config/skill_extraction.yaml or pass config_path explicitly."
        )

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid skill extraction config in {path}: expected mapping")

    return SkillExtractionConfig(
        light_head=_as_normalized_set(payload.get("light_head", [])),
        exclude_list=_as_normalized_set(payload.get("exclude_list", [])),
        single_token_allowlist=_as_normalized_set(
            payload.get("single_token_allowlist", [])
        ),
        discourse_markers=_as_normalized_list(payload.get("discourse_markers", [])),
        vague_tail_nouns=_as_normalized_set(
            payload.get("vague_tail_nouns", payload.get("vague_outcome_nouns", []))
        ),
        soft_skill_markers=_as_normalized_list(payload.get("soft_skill_markers", [])),
        academic_field_nouns=_as_normalized_set(payload.get("academic_field_nouns", [])),
        light_modifier=_as_normalized_set(payload.get("light_modifier", [])),
    )


def _as_normalized_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(item).strip().lower() for item in values if str(item).strip()}


def _as_normalized_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip().lower()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
