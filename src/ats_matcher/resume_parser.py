from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from statistics import median
from typing import List, Optional

from docx import Document

from ats_matcher.models import Bullet, ResumeData, Role, Section
from ats_matcher.utils import stable_bullet_id

# PDF magic bytes: %PDF
_PDF_MAGIC = b"%PDF"

# Bullet characters recognised across PDFs
_BULLET_CHARS = set("-•·▪▸►✓*∗◦‣–")


@dataclass
class Line:
    """Intermediate representation of a single visual line from a PDF page."""

    text: str
    x0: float  # left edge (indentation proxy)
    font_size: float  # median font size of words on this line
    is_bold: bool  # any word uses a Bold font variant
    has_bullet: bool  # starts with a bullet character
    y_gap: float  # vertical gap from previous line's top
    page_idx: int = 0
    top: float = 0.0  # absolute y position on page


def _extract_lines_from_pdf(pdf_bytes: bytes) -> List[Line]:
    """Extract word-level data from PDF and group into Lines."""
    import pdfplumber

    all_lines: List[Line] = []
    prev_top = 0.0

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            words = page.extract_words(extra_attrs=["fontname", "size"])
            if not words:
                continue

            # Group words into visual lines by top coordinate (±2pt)
            grouped: List[List[dict]] = []
            current_group: List[dict] = []
            current_top: Optional[float] = None

            for w in words:
                if current_top is not None and abs(w["top"] - current_top) > 2:
                    if current_group:
                        grouped.append(current_group)
                    current_group = []
                    current_top = None

                current_group.append(w)
                if current_top is None:
                    current_top = w["top"]

            if current_group:
                grouped.append(current_group)

            # Merge lines with negative or very small gap (same visual line,
            # e.g. bullet char rendered as separate word at different baseline)
            merged: List[List[dict]] = []
            for group in grouped:
                if merged and abs(group[0]["top"] - merged[-1][0]["top"]) <= 3:
                    merged[-1].extend(group)
                else:
                    merged.append(group)

            for line_words in merged:
                # Sort words left-to-right
                line_words.sort(key=lambda w: w["x0"])

                text = " ".join(w["text"] for w in line_words).strip()
                if not text:
                    continue

                x0 = line_words[0]["x0"]
                top = line_words[0]["top"]
                sizes = [w["size"] for w in line_words]
                med_size = median(sizes) if sizes else 0.0
                fonts = {w["fontname"] for w in line_words}
                is_bold = any("Bold" in f or "bold" in f for f in fonts)
                first_char = text[0] if text else ""
                has_bullet = first_char in _BULLET_CHARS

                y_gap = top - prev_top if prev_top > 0 else 0.0
                prev_top = top

                all_lines.append(
                    Line(
                        text=text,
                        x0=x0,
                        font_size=med_size,
                        is_bold=is_bold,
                        has_bullet=has_bullet,
                        y_gap=y_gap,
                        page_idx=page_idx,
                        top=top,
                    )
                )

    return all_lines


def _cluster_x0(values: List[float], tolerance: float = 8.0) -> List[float]:
    """Cluster x0 values into distinct indentation levels.
    Returns sorted list of cluster centroids."""
    if not values:
        return []

    sorted_vals = sorted(set(round(v, 1) for v in values))
    clusters: List[List[float]] = [[sorted_vals[0]]]

    for v in sorted_vals[1:]:
        if v - clusters[-1][-1] <= tolerance:
            clusters[-1].append(v)
        else:
            clusters.append([v])

    return [sum(c) / len(c) for c in clusters]


def _get_indent_level(x0: Optional[float], levels: List[float]) -> int:
    """Return the indent level index (0 = leftmost) for a given x0 value."""
    if x0 is None or not levels:
        return 0
    best = 0
    best_dist = abs(x0 - levels[0])
    for i, lvl in enumerate(levels[1:], 1):
        dist = abs(x0 - lvl)
        if dist < best_dist:
            best = i
            best_dist = dist
    return best


class ResumeParser:
    def __init__(self) -> None:
        pass

    def parse(self, file_bytes: bytes) -> ResumeData:
        if file_bytes[:4] == _PDF_MAGIC:
            return self._parse_pdf(file_bytes)
        return self._parse_docx(file_bytes)

    # ── DOCX ────────────────────────────────────────────────────────────────

    def _parse_docx(self, docx_bytes: bytes) -> ResumeData:
        document = Document(BytesIO(docx_bytes))
        sections: List[Section] = []
        bullet_index = {}

        current_section: Optional[Section] = None
        current_role: Optional[Role] = None
        bullet_counter = 0
        last_bullet: Optional[Bullet] = None

        for idx, paragraph in enumerate(document.paragraphs):
            text = paragraph.text.strip()
            if not text:
                continue

            style_name = paragraph.style.name if paragraph.style else ""

            if self._is_heading(style_name, text):
                current_section = Section(title=text, roles=[])
                sections.append(current_section)
                current_role = None
                last_bullet = None
                continue

            if self._is_bullet(paragraph, style_name, text):
                if current_section is None:
                    current_section = Section(title="General", roles=[])
                    sections.append(current_section)

                if current_role is None:
                    current_role = Role(title="Role", bullets=[])
                    current_section.roles.append(current_role)

                bullet_id = stable_bullet_id(
                    current_section.title, current_role.title, bullet_counter
                )
                bullet_counter += 1
                bullet = Bullet(
                    bullet_id=bullet_id,
                    text=text,
                    paragraph_index=idx,
                    section_title=current_section.title,
                    role_title=current_role.title,
                )
                current_role.bullets.append(bullet)
                bullet_index[bullet_id] = bullet
                last_bullet = bullet
                continue

            # ── Continuation merging ──
            # If previous was a bullet and current is plain text (no heading style,
            # no bullet markers, no numPr), merge into the previous bullet.
            # This handles wrapped .docx bullets where continuation <w:p> elements
            # lack numPr.
            if last_bullet is not None and self._is_continuation(paragraph, style_name, text):
                last_bullet.text = last_bullet.text + " " + text
                continue

            if current_section is None:
                current_section = Section(title="General", roles=[])
                sections.append(current_section)

            current_role = Role(title=text, bullets=[])
            current_section.roles.append(current_role)
            last_bullet = None

        return ResumeData(sections=sections, bullet_index=bullet_index)

    # ── PDF ─────────────────────────────────────────────────────────────────

    # Known section heading keywords (case-insensitive)
    _HEADING_KEYWORDS = {
        "experience",
        "education",
        "skills",
        "summary",
        "objective",
        "projects",
        "certifications",
        "publications",
        "awards",
        "honors",
        "activities",
        "interests",
        "references",
        "professional experience",
        "work experience",
        "professional summary",
        "technical skills",
        "core competencies",
        "volunteer",
        "volunteering",
        "leadership",
        "training",
        "coursework",
        "significant coursework",
        "computer skills",
        "selected projects",
        "additional information",
        "languages",
        "accomplishments",
        "honours and awards",
        "honors and awards",
        "education and awards",
        "intercollegiate athletics",
        "course projects",
        "research",
        "professional development",
        "memberships",
        "extracurricular",
        "extracurricular activities",
        "campus involvement",
        "volunteer experience",
        "leadership experience",
        "selected",
        "athletics",
    }

    def _parse_pdf(self, pdf_bytes: bytes) -> ResumeData:
        lines = _extract_lines_from_pdf(pdf_bytes)
        if not lines:
            return ResumeData(sections=[], bullet_index={}, low_confidence=True)

        # Compute median body font size (most common size = body text)
        all_sizes = [ln.font_size for ln in lines if ln.font_size > 0]
        if not all_sizes:
            return ResumeData(sections=[], bullet_index={}, low_confidence=True)
        body_size = median(all_sizes)

        # Compute median line spacing for gap-based heading detection
        gaps = [ln.y_gap for ln in lines if ln.y_gap > 0]
        median_gap = median(gaps) if gaps else 12.0

        # Compute indentation clusters for bullet/continuation detection
        x0_values = [ln.x0 for ln in lines]
        indent_levels = _cluster_x0(x0_values)

        # Classify each line
        sections: List[Section] = []
        bullet_index = {}
        current_section: Optional[Section] = None
        current_role: Optional[Role] = None
        bullet_counter = 0
        last_bullet: Optional[Bullet] = None
        last_bullet_x0: Optional[float] = None

        for idx, ln in enumerate(lines):
            text = ln.text.strip()
            if not text:
                continue

            # ── Heading continuation ──
            # If previous line was a heading with no roles yet and this line is
            # short, at same x0, same style → merge into heading
            # (handles "EDUCATION" + "AND AWARDS", "INTER-" + "COLLEGIATE" etc.)
            if (
                current_section is not None
                and current_role is None
                and len(current_section.roles) == 0
                and len(text) <= 30
                and idx > 0
                and abs(ln.x0 - lines[idx - 1].x0) < 5
                and not ln.has_bullet
            ):
                # Check if heading title ends with hyphen (word break)
                if current_section.title.endswith("-"):
                    current_section.title = current_section.title + text
                else:
                    current_section.title += " " + text
                continue

            # ── Heading detection (multi-signal) ──
            if self._pdf_is_heading_multi(ln, body_size, median_gap):
                current_section = Section(title=text, roles=[])
                sections.append(current_section)
                current_role = None
                last_bullet = None
                last_bullet_x0 = None
                continue

            # ── Bullet detection ──
            if ln.has_bullet:
                cleaned = text.lstrip("".join(_BULLET_CHARS) + " ").strip()
                if not cleaned:
                    continue

                if current_section is None:
                    current_section = Section(title="General", roles=[])
                    sections.append(current_section)
                if current_role is None:
                    current_role = Role(title="Role", bullets=[])
                    current_section.roles.append(current_role)

                bullet_id = stable_bullet_id(
                    current_section.title, current_role.title, bullet_counter
                )
                bullet_counter += 1
                bullet = Bullet(
                    bullet_id=bullet_id,
                    text=cleaned,
                    paragraph_index=idx,
                    section_title=current_section.title,
                    role_title=current_role.title,
                )
                current_role.bullets.append(bullet)
                bullet_index[bullet_id] = bullet
                last_bullet = bullet
                last_bullet_x0 = ln.x0
                continue

            # ── Continuation detection ──
            # If previous was a bullet/continuation and this line is indented
            # at same or greater level, no bullet char, not bold → merge
            if last_bullet is not None and not ln.is_bold:
                indent = _get_indent_level(ln.x0, indent_levels)
                bullet_indent = _get_indent_level(last_bullet_x0, indent_levels)
                if indent >= bullet_indent:
                    last_bullet.text = last_bullet.text + " " + text
                    continue

            # ── Role title detection ──
            # Bold, short, not a heading, at margin or slightly indented → role title
            # Also: any non-bullet non-heading text after a heading → role title
            if current_section is None:
                current_section = Section(title="General", roles=[])
                sections.append(current_section)

            current_role = Role(title=text, bullets=[])
            current_section.roles.append(current_role)
            last_bullet = None
            last_bullet_x0 = None

        return ResumeData(
            sections=sections, bullet_index=bullet_index, low_confidence=False
        )

    def _pdf_is_heading_multi(
        self, ln: Line, body_size: float, median_gap: float
    ) -> bool:
        """Multi-signal heading classification. Returns True if ≥2 signals agree,
        or font_size alone is ≥4pt larger than body."""
        text = ln.text.strip()
        if not text or len(text) > 60:
            return False

        signals = 0

        # Signal 1: Font size notably larger than body
        # Use 1.5pt threshold (not 2pt) to handle median floating-point drift
        if ln.font_size >= body_size + 1.5:
            signals += 1
            # Strong signal: ≥4pt larger → heading on its own
            if ln.font_size >= body_size + 4:
                return True

        # Signal 2: Bold + short text
        if ln.is_bold and len(text) <= 40:
            signals += 1

        # Signal 3: Known heading keyword
        text_lower = text.lower().strip()
        # Strip trailing colons, dashes for matching
        text_clean = text_lower.rstrip(":- ")
        if text_clean in self._HEADING_KEYWORDS:
            signals += 1

        # Signal 4: ALL-CAPS
        if text.isupper() and len(text) <= 40:
            signals += 1

        # Signal 5: Large y_gap (≥1.5× median spacing) suggests section break
        if ln.y_gap > median_gap * 1.5 and ln.y_gap > 0:
            signals += 1

        return signals >= 2

    # ── Helpers (DOCX) ───────────────────────────────────────────────────────

    def _is_heading(self, style_name: str, text: str) -> bool:
        if style_name.lower().startswith("heading"):
            return True
        if text.isupper() and len(text) <= 40:
            return True
        # Known heading keyword match (for docs without heading styles)
        text_clean = text.lower().strip().rstrip(":- ")
        if text_clean in self._HEADING_KEYWORDS:
            return True
        return False

    def _is_bullet(self, paragraph, style_name: str, text: str) -> bool:
        if "list" in style_name.lower():
            return True
        if text.startswith(("- ", "• ")):
            return True
        if paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None:
            return True
        return False

    def _is_continuation(self, paragraph, style_name: str, text: str) -> bool:
        """Check if a paragraph is a continuation of a previous bullet.
        True when: not a heading, not a bullet, not bold, and has indentation
        or is plain body text."""
        # If it looks like a heading or bullet, it's not a continuation
        if self._is_heading(style_name, text):
            return False
        if self._is_bullet(paragraph, style_name, text):
            return False
        # Check for bold runs — bold text is likely a role title, not continuation
        if paragraph.runs and all(r.bold for r in paragraph.runs if r.text.strip()):
            return False
        # Check indentation — if indented at same or greater level, likely continuation
        left_indent = paragraph.paragraph_format.left_indent
        if left_indent is not None and left_indent.pt > 0:
            return True
        # Even without explicit indent, if text is short-ish plain text
        # following a bullet, treat as continuation (handles wrapped bullets
        # where Word doesn't preserve indent in the XML)
        return True

