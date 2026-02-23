from __future__ import annotations

from ats_matcher.render.rewrite_utils import (
    compute_coverage,
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
