from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from ats_matcher.models import ResumeData
from ats_matcher.render.rewrite_utils import (
    ordered_bullets_for_role,
    sanitize_editor_text,
    strip_leading_bullet_prefixes,
)


@dataclass(frozen=True)
class ResumeTemplateConfig:
    page_width: float = A4[0]
    page_height: float = A4[1]
    margin_top: float = 16 * mm
    margin_bottom: float = 16 * mm
    margin_left: float = 18 * mm
    margin_right: float = 18 * mm
    font_name: str = "Helvetica"
    font_bold: str = "Helvetica-Bold"
    name_size: float = 16.0
    heading_size: float = 11.0
    body_size: float = 10.0
    line_spacing: float = 1.15
    section_space_before: float = 6.0
    section_space_after: float = 3.0
    bullet_glyph: str = "•"
    bullet_gap: float = 10.0
    bullet_hanging_indent: float = 18.0


DEFAULT_TEMPLATE_CONFIG = ResumeTemplateConfig()


def render_resume_pdf(
    resume: ResumeData,
    edits: dict[str, str],
    full_name: str,
    contact_line: str,
    bullet_order_by_role: dict[str, list[str]] | None = None,
    config: ResumeTemplateConfig = DEFAULT_TEMPLATE_CONFIG,
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(config.page_width, config.page_height))

    body_leading = config.body_size * config.line_spacing
    heading_leading = config.heading_size * config.line_spacing
    name_leading = config.name_size * config.line_spacing
    content_width = config.page_width - config.margin_left - config.margin_right
    y = config.page_height - config.margin_top

    def start_page() -> float:
        nonlocal pdf
        y_pos = config.page_height - config.margin_top
        y_pos = draw_header(y_pos)
        return y_pos

    def ensure_space(required: float, current_y: float) -> float:
        if current_y - required >= config.margin_bottom:
            return current_y
        pdf.showPage()
        return start_page()

    def draw_header(current_y: float) -> float:
        name = (full_name or "Your Name").strip() or "Your Name"
        contact = contact_line.strip()

        pdf.setFont(config.font_bold, config.name_size)
        pdf.drawString(config.margin_left, current_y, name)
        current_y -= name_leading

        if contact:
            pdf.setFont(config.font_name, config.body_size)
            wrapped = _wrap_text(
                text=contact,
                font_name=config.font_name,
                font_size=config.body_size,
                max_width=content_width,
            )
            for line in wrapped:
                current_y = ensure_space(body_leading, current_y)
                pdf.drawString(config.margin_left, current_y, line)
                current_y -= body_leading

        current_y -= 4.0
        return current_y

    def draw_section_heading(title: str, current_y: float) -> float:
        current_y = ensure_space(
            config.section_space_before + heading_leading + config.section_space_after,
            current_y,
        )
        current_y -= config.section_space_before
        pdf.setFont(config.font_bold, config.heading_size)
        pdf.drawString(config.margin_left, current_y, title)
        current_y -= heading_leading
        current_y -= config.section_space_after
        return current_y

    def draw_role_title(role_title: str, current_y: float) -> float:
        wrapped = _wrap_text(
            text=role_title,
            font_name=config.font_bold,
            font_size=config.body_size,
            max_width=content_width,
        )
        pdf.setFont(config.font_bold, config.body_size)
        for line in wrapped:
            current_y = ensure_space(body_leading, current_y)
            pdf.drawString(config.margin_left, current_y, line)
            current_y -= body_leading
        return current_y

    def draw_bullet_line(text: str, current_y: float) -> float:
        normalized = strip_leading_bullet_prefixes(text)
        if not normalized:
            return current_y

        bullet_x = config.margin_left
        text_x = config.margin_left + config.bullet_hanging_indent
        max_width = content_width - config.bullet_hanging_indent
        wrapped = _wrap_text(
            text=normalized,
            font_name=config.font_name,
            font_size=config.body_size,
            max_width=max_width,
        )
        if not wrapped:
            return current_y

        current_y = ensure_space(body_leading, current_y)
        pdf.setFont(config.font_name, config.body_size)
        pdf.drawString(bullet_x, current_y, config.bullet_glyph)
        pdf.drawString(text_x, current_y, wrapped[0])
        current_y -= body_leading

        for continuation in wrapped[1:]:
            current_y = ensure_space(body_leading, current_y)
            pdf.drawString(text_x, current_y, continuation)
            current_y -= body_leading
        return current_y

    y = start_page()
    for section_idx, section in enumerate(resume.sections):
        if not section.roles:
            continue
        y = draw_section_heading(section.title, y)
        for role_idx, role in enumerate(section.roles):
            role_title = (role.title or "").strip()
            if role_title:
                y = draw_role_title(role_title, y)
            role_key = f"{section_idx}:{role_idx}"
            ordered_bullets = ordered_bullets_for_role(
                role=role,
                role_key=role_key,
                bullet_order_by_role=bullet_order_by_role,
            )
            for bullet in ordered_bullets:
                bullet_text = edits.get(bullet.bullet_id, bullet.text)
                bullet_text = sanitize_editor_text(bullet_text)
                y = draw_bullet_line(bullet_text, y)
            y -= 2.0

    pdf.save()
    return buffer.getvalue()


def _wrap_text(
    text: str, font_name: str, font_size: float, max_width: float
) -> list[str]:
    stripped = " ".join(text.split())
    if not stripped:
        return []

    words = stripped.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue

        lines.append(current)
        if pdfmetrics.stringWidth(word, font_name, font_size) <= max_width:
            current = word
            continue

        segments = _split_long_word(word, font_name, font_size, max_width)
        lines.extend(segments[:-1])
        current = segments[-1]

    lines.append(current)
    return lines


def _split_long_word(
    word: str, font_name: str, font_size: float, max_width: float
) -> list[str]:
    parts: list[str] = []
    current = ""
    for char in word:
        candidate = f"{current}{char}"
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = char
    if current:
        parts.append(current)
    return parts or [word]
