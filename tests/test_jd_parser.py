from __future__ import annotations

import pytest

from ats_matcher.jd_parser import JDParser


@pytest.fixture(scope="module")
def parser() -> JDParser:
    try:
        return JDParser(
            model_name="en_core_web_sm",
            esco_skill_phrases=["machine learning", "project management"],
        )
    except OSError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"spaCy model unavailable: {exc}")


def test_light_head_stripping_removes_generic_head(parser: JDParser) -> None:
    text = "Hands-on work in enterprise performance area and budget planning."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}

    assert "enterprise performance" in normalized
    assert "area" not in normalized


def test_generic_years_terms_are_filtered(parser: JDParser) -> None:
    text = (
        "Candidates need minimum 5 years of working experience in relevant "
        "environments with stakeholders."
    )
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}

    assert "years" not in normalized
    assert "minimum" not in normalized
    assert "working experience" not in normalized


def test_esco_entities_are_extracted(parser: JDParser) -> None:
    text = "The role requires machine learning in production systems."
    components = parser.extract_skill_components(text)
    normalized_esco = {item.lower() for item in components["esco_skills"]}

    assert "machine learning" in normalized_esco


def test_allowlisted_single_token_can_pass(parser: JDParser) -> None:
    text = "Strong SQL is required for the role."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}

    assert "sql" in normalized


def test_newline_boundary_avoids_cross_line_phrase(parser: JDParser) -> None:
    text = "Experience with AI\nCompetency in two or more of the following: SQL, AWS"
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}

    assert "ai competency" not in normalized
    assert "ai" in normalized


def test_discourse_marker_is_removed_from_phrase(parser: JDParser) -> None:
    text = "Tools include e.g. VBA, SQL, and AWS."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}

    assert "e.g. vba" not in normalized
    assert "vba" in normalized


def test_allowlisted_short_token_not_marked_too_short(parser: JDParser) -> None:
    text = "AI systems experience with model deployment"
    components = parser.extract_skill_components(text, debug=True)
    debug_events = components.get("debug_events", [])

    ai_too_short_drops = [
        event
        for event in debug_events
        if event.get("candidate", "").lower() == "ai"
        and event.get("action") == "dropped"
        and event.get("reason") == "too_short"
    ]
    assert not ai_too_short_drops
