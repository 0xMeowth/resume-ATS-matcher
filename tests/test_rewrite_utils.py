from __future__ import annotations

from ats_matcher.models import Bullet, ResumeData, Role, Section
from ats_matcher.render.rewrite_utils import (
    compute_coverage,
    extract_resume_text,
    sanitize_editor_text,
    strip_leading_bullet_prefixes,
)


def test_strip_leading_bullet_prefixes_repeated() -> None:
    assert (
        strip_leading_bullet_prefixes("  • - —  Build dashboards") == "Build dashboards"
    )


def test_compute_coverage_strict_for_ai_boundary() -> None:
    resume_text = "Evaluated on-chain data and protocol mechanisms"
    covered, missing = compute_coverage(["AI", "protocol"], resume_text)

    assert "protocol" in covered
    assert "AI" in missing


def test_compute_coverage_toolish_terms() -> None:
    resume_text = "Built .NET services and improved CI/CD pipelines"
    covered, missing = compute_coverage([".NET", "CI/CD", "AWS"], resume_text)

    assert ".NET" in covered
    assert "CI/CD" in covered
    assert "AWS" in missing


def test_sanitize_editor_text_trims_trailing_newline_only() -> None:
    assert sanitize_editor_text("Line one\n") == "Line one"
    assert sanitize_editor_text("Line one\nLine two\n") == "Line one\nLine two"


def test_extract_resume_text_respects_bullet_order() -> None:
    bullet_a = Bullet(
        bullet_id="a",
        text="First",
        paragraph_index=0,
        section_title="Experience",
        role_title="Engineer",
    )
    bullet_b = Bullet(
        bullet_id="b",
        text="Second",
        paragraph_index=1,
        section_title="Experience",
        role_title="Engineer",
    )
    resume = ResumeData(
        sections=[
            Section(
                title="Experience",
                roles=[Role(title="Engineer", bullets=[bullet_a, bullet_b])],
            )
        ],
        bullet_index={"a": bullet_a, "b": bullet_b},
    )

    text = extract_resume_text(
        resume=resume,
        edits={},
        bullet_order_by_role={"0:0": ["b", "a"]},
    )
    assert "Second\nFirst" in text
