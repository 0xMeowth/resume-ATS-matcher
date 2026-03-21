from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from ats_matcher.resume_parser import ResumeParser, _PDF_MAGIC

FIXTURES = Path(__file__).parent / "fixtures" / "resumes"


def _make_pdf(text: str) -> bytes:
    """Return minimal valid PDF bytes containing *text* using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 750
    for line in text.splitlines():
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def _make_docx(text: str) -> bytes:
    """Return minimal valid .docx bytes containing *text* using python-docx."""
    from docx import Document

    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Magic-byte detection ──────────────────────────────────────────────────────

def test_pdf_magic_bytes_detected():
    pdf_bytes = _make_pdf("EXPERIENCE\n- Built something")
    assert pdf_bytes[:4] == _PDF_MAGIC


def test_docx_magic_bytes_not_pdf():
    docx_bytes = _make_docx("EXPERIENCE")
    assert docx_bytes[:4] != _PDF_MAGIC


# ── low_confidence flag ───────────────────────────────────────────────────────

def test_pdf_parse_not_low_confidence_with_rich_extraction():
    pdf_bytes = _make_pdf("EXPERIENCE\n- Built something great")
    parser = ResumeParser()
    result = parser.parse(pdf_bytes)
    # Rich PDF extraction now provides enough signals for confident parsing
    assert result.low_confidence is False


def test_docx_parse_does_not_set_low_confidence():
    docx_bytes = _make_docx("EXPERIENCE")
    parser = ResumeParser()
    result = parser.parse(docx_bytes)
    assert result.low_confidence is False


# ── No crash on minimal PDF ───────────────────────────────────────────────────

def test_pdf_parse_does_not_crash_on_minimal_input():
    pdf_bytes = _make_pdf("")
    parser = ResumeParser()
    result = parser.parse(pdf_bytes)
    assert result is not None
    assert isinstance(result.sections, list)
    assert isinstance(result.bullet_index, dict)


def test_pdf_parse_does_not_crash_on_realistic_input():
    content = "\n".join([
        "EXPERIENCE",
        "Senior Engineer | Acme Corp | 2021-2024",
        "- Designed distributed systems serving 10M users",
        "- Led migration from monolith to microservices",
        "SKILLS",
        "- Python, Go, Kubernetes, PostgreSQL",
    ])
    pdf_bytes = _make_pdf(content)
    parser = ResumeParser()
    result = parser.parse(pdf_bytes)
    assert result.low_confidence is False
    assert len(result.sections) > 0


# ── Regression tests with real PDF fixtures ──────────────────────────────────

_SINGLE_COLUMN_PDFS = ["john_smith", "omkar_pathak", "Layla_Martin_Resume", "resume_Meyer"]
_ALL_PDFS = _SINGLE_COLUMN_PDFS + ["Brendan_Herger_Resume", "SGresume-1"]


@pytest.mark.parametrize("name", _ALL_PDFS)
def test_pdf_fixture_parses_without_error(name):
    """Every test PDF should parse without crashing."""
    pdf_path = FIXTURES / f"{name}.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Fixture {name}.pdf not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    assert result is not None
    assert isinstance(result.sections, list)


@pytest.mark.parametrize("name", _SINGLE_COLUMN_PDFS)
def test_pdf_fixture_has_sections_and_bullets(name):
    """Single-column PDFs should produce ≥1 section and ≥3 bullets."""
    pdf_path = FIXTURES / f"{name}.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Fixture {name}.pdf not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    assert len(result.sections) >= 1
    total_bullets = sum(
        len(r.bullets) for s in result.sections for r in s.roles
    )
    assert total_bullets >= 3, f"Expected ≥3 bullets, got {total_bullets}"


def test_john_smith_headings():
    """john_smith.pdf uses ALL-CAPS headings — verify key sections detected."""
    pdf_path = FIXTURES / "john_smith.pdf"
    if not pdf_path.exists():
        pytest.skip("Fixture not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    titles = {s.title for s in result.sections}
    for expected in ["WORK EXPERIENCE", "EDUCATION", "HONORS"]:
        assert expected in titles, f"Missing section: {expected}"


def test_john_smith_bullet_continuation():
    """Wrapped bullets in john_smith.pdf should be merged, not orphaned."""
    pdf_path = FIXTURES / "john_smith.pdf"
    if not pdf_path.exists():
        pytest.skip("Fixture not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    # "fundraiser for 200 attendees" should be part of a bullet, not a role title
    role_titles = [r.title for s in result.sections for r in s.roles]
    orphan_fragments = [t for t in role_titles if "fundraiser" in t.lower()]
    assert len(orphan_fragments) == 0, (
        f"Continuation line 'fundraiser...' orphaned as role title: {orphan_fragments}"
    )


def test_omkar_heading_detection():
    """omkar_pathak.pdf uses mixed-case headings with larger font — verify detection."""
    pdf_path = FIXTURES / "omkar_pathak.pdf"
    if not pdf_path.exists():
        pytest.skip("Fixture not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    titles = {s.title for s in result.sections}
    for expected in ["Experience", "Education", "Projects"]:
        assert expected in titles, f"Missing section: {expected}"


def test_omkar_sub_bullet_detection():
    """omkar_pathak.pdf uses ∗ sub-bullets — these should be detected as bullets."""
    pdf_path = FIXTURES / "omkar_pathak.pdf"
    if not pdf_path.exists():
        pytest.skip("Fixture not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    all_bullets = [
        b.text for s in result.sections for r in s.roles for b in r.bullets
    ]
    # Sub-bullets about platforms should be captured
    supply_chain = [b for b in all_bullets if "Supply Chain" in b]
    assert len(supply_chain) >= 1, "Sub-bullet about Supply Chain not found"


def test_layla_heading_merge():
    """Layla's multi-line headings should be merged (e.g. EDUCATION AND AWARDS)."""
    pdf_path = FIXTURES / "Layla_Martin_Resume.pdf"
    if not pdf_path.exists():
        pytest.skip("Fixture not found")
    parser = ResumeParser()
    result = parser.parse(pdf_path.read_bytes())
    titles = {s.title for s in result.sections}
    # "EDUCATION" and "AND AWARDS" should be merged
    education_titles = [t for t in titles if "EDUCATION" in t]
    assert any("AWARDS" in t for t in education_titles), (
        f"Expected merged 'EDUCATION AND AWARDS', got: {education_titles}"
    )
