from __future__ import annotations

from io import BytesIO

import pytest

from ats_matcher.resume_parser import ResumeParser, _PDF_MAGIC


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

def test_pdf_parse_sets_low_confidence():
    pdf_bytes = _make_pdf("EXPERIENCE\n- Built something great")
    parser = ResumeParser()
    result = parser.parse(pdf_bytes)
    assert result.low_confidence is True


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
    assert result.low_confidence is True
    assert len(result.sections) > 0
