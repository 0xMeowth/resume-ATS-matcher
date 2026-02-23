from __future__ import annotations

from ats_matcher.render.pdf_resume import DEFAULT_TEMPLATE_CONFIG, render_resume_pdf
from ats_matcher.render.rewrite_utils import (
    compute_coverage,
    extract_resume_text,
    ordered_bullets_for_role,
    sanitize_editor_text,
    split_newline_terms,
    strip_leading_bullet_prefixes,
)

__all__ = [
    "DEFAULT_TEMPLATE_CONFIG",
    "compute_coverage",
    "extract_resume_text",
    "ordered_bullets_for_role",
    "render_resume_pdf",
    "sanitize_editor_text",
    "split_newline_terms",
    "strip_leading_bullet_prefixes",
]
