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
    text = "Hands-on work in enterprise architecture area and budget planning."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}

    assert "enterprise architecture" in normalized
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


# --- Phase 9A: Text preprocessing ---


def test_html_tags_are_stripped(parser: JDParser) -> None:
    text = "<p>Experience with <strong>Python</strong> and <br/>data pipelines</p>"
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert not any("<" in s or ">" in s for s in normalized)
    assert "python" in normalized


def test_urls_are_stripped(parser: JDParser) -> None:
    text = "Apply at https://www.example.com/careers and demonstrate SQL skills."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert not any("https" in s for s in normalized)
    assert "sql" in normalized


def test_emails_are_stripped(parser: JDParser) -> None:
    text = "Contact hr@company.com for Python developer role."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert not any("@" in s for s in normalized)


# --- Phase 9B: Exclusion list additions ---


def test_education_terms_filtered(parser: JDParser) -> None:
    text = "Bachelor's degree in Computer Science with Python experience."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert "bachelor's degree" not in normalized
    assert "degree" not in normalized
    assert "bachelor" not in normalized


def test_company_identifiers_filtered(parser: JDParser) -> None:
    text = "NMG Financial Services Consulting Pte Ltd requires SQL skills."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert "pte" not in normalized
    assert "ltd" not in normalized


def test_slash_compound_stays_single_token(parser: JDParser) -> None:
    text = "Experience with CI/CD pipelines and AI/ML frameworks."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert "ci/cd" in normalized or "ci/cd pipelines" in normalized


# --- Phase 9C: Extraction logic fixes ---


def test_substring_suppression_keeps_independent_shorter_phrase(parser: JDParser) -> None:
    """C1: 'data governance' should survive when both it and 'data governance frameworks' appear."""
    text = (
        "Experience with data governance frameworks. "
        "Responsible for data governance across teams."
    )
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert "data governance" in normalized


def test_lemma_dedup_collapses_plural(parser: JDParser) -> None:
    """C2: 'strategy framework' and 'strategy frameworks' should collapse to one entry."""
    text = (
        "Develop strategy frameworks for the business. "
        "Each strategy framework should be documented."
    )
    skills = parser.extract_skill_terms(text)
    normalized = [item.lower() for item in skills]
    framework_entries = [s for s in normalized if "strategy framework" in s]
    assert len(framework_entries) == 1


def test_company_name_filtered(parser: JDParser) -> None:
    """C3: Company name from header should not be extracted as a skill."""
    text = "Title: Software Engineer\nCompany: Accenture Digital Solutions\n\nRequires Python and SQL."
    skills = parser.extract_skill_terms(text)
    normalized = {item.lower() for item in skills}
    assert "accenture" not in normalized
    assert "accenture digital solutions" not in normalized


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
