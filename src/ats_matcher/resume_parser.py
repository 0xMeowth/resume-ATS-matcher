from __future__ import annotations

import re
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

# Contact info patterns
_PHONE_RE = re.compile(
    r"(?:\+\d[\d\s\-]{8,}|\(?\d{3}\)?[\s.\-·]?\d{3}[\s.\-·]?\d{4})"
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|linkedin\.com\S*|github\.com\S*", re.I)


def _is_contact_line(text: str) -> bool:
    """Return True if the line contains phone, email, or URL patterns."""
    return bool(_PHONE_RE.search(text) or _EMAIL_RE.search(text) or _URL_RE.search(text))


def _normalize_spaced_heading(text: str) -> str:
    """Collapse spaced-letter headings: 'E X P E R I E N C E' → 'EXPERIENCE',
    'S K I L L S & I N T E R E S T S' → 'SKILLS & INTERESTS'."""
    parts = text.split()
    if len(parts) < 3:
        return text
    single_count = sum(1 for p in parts if len(p) == 1)
    if single_count / len(parts) < 0.7:
        return text
    # Collapse consecutive single-letter parts into words,
    # keep multi-char parts (like '&') as separators
    result = []
    current_word = []
    for p in parts:
        if len(p) == 1 and p.isalpha():
            current_word.append(p)
        else:
            if current_word:
                result.append("".join(current_word))
                current_word = []
            result.append(p)
    if current_word:
        result.append("".join(current_word))
    return " ".join(result)


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

    # Sort by visual position (page, then top-to-bottom) to fix PDFs
    # where the content stream order differs from the visual layout.
    all_lines.sort(key=lambda ln: (ln.page_idx, ln.top))

    # Recompute y_gap after sorting
    for i, ln in enumerate(all_lines):
        if i == 0:
            ln.y_gap = 0.0
        else:
            prev = all_lines[i - 1]
            if ln.page_idx != prev.page_idx:
                ln.y_gap = 0.0  # new page — no meaningful gap
            else:
                ln.y_gap = ln.top - prev.top

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
        "skills & interests",
        "skills and interests",
    }

    def _text_contains_heading_keyword(self, text: str) -> bool:
        """Check if text contains any heading keyword (word-level match)."""
        text_clean = text.lower().strip().rstrip(":- ")
        # Exact match first
        if text_clean in self._HEADING_KEYWORDS:
            return True
        # Word-level: split on non-alpha and check if any keyword appears
        words = set(re.split(r"[^a-z]+", text_clean))
        return bool(words & self._HEADING_KEYWORDS)

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

        # ── Pre-heading pass: find first real heading and group header lines ──
        first_heading_idx = None
        for i, ln in enumerate(lines):
            text = ln.text.strip()
            if not text:
                continue
            normalized = _normalize_spaced_heading(text)
            if self._text_contains_heading_keyword(normalized):
                first_heading_idx = i
                break
            # Also check multi-signal heading, but only if it has a keyword
            # (name lines are often large+bold and pass heading detection)
            if self._pdf_is_heading_multi(ln, body_size, median_gap):
                if self._text_contains_heading_keyword(normalized):
                    first_heading_idx = i
                    break

        # Build header section from pre-heading lines
        sections: List[Section] = []
        bullet_index = {}
        bullet_counter = 0
        start_idx = 0

        if first_heading_idx is not None and first_heading_idx > 0:
            pre_lines = lines[:first_heading_idx]
            # Name = largest font line (or first line if tied)
            name_line = max(pre_lines, key=lambda ln: ln.font_size)
            name = name_line.text.strip()
            # Contact lines = everything else
            contact_bullets = []
            for ln in pre_lines:
                t = ln.text.strip()
                if not t or t == name:
                    continue
                bid = stable_bullet_id(name, "", bullet_counter)
                bullet_counter += 1
                b = Bullet(
                    bullet_id=bid,
                    text=t,
                    paragraph_index=-1,
                    section_title=name,
                    role_title="",
                )
                contact_bullets.append(b)
                bullet_index[bid] = b
            header_role = Role(title=None, bullets=contact_bullets)
            header_section = Section(title=name, roles=[header_role] if contact_bullets else [])
            sections.append(header_section)
            start_idx = first_heading_idx

        # Classify remaining lines
        current_section: Optional[Section] = sections[0] if sections else None
        current_role: Optional[Role] = None
        last_bullet: Optional[Bullet] = None
        last_bullet_x0: Optional[float] = None
        inside_known_section = False  # prevents false section splits
        heading_x0: Optional[float] = None  # x0 of last heading line
        heading_top: Optional[float] = None  # top of last heading line

        for idx, ln in enumerate(lines[start_idx:], start=start_idx):
            text = ln.text.strip()
            if not text:
                continue

            # Normalise spaced-letter headings for keyword matching
            normalized = _normalize_spaced_heading(text)
            is_spaced = normalized != text

            # ── Heading continuation ──
            # Merge short ALL-CAPS lines near the heading's x0/top into the
            # heading title (handles "EDUCATION" + "AND AWARDS" across columns).
            # Skip if the text is itself a heading keyword (it's a new section).
            if (
                current_section is not None
                and heading_x0 is not None
                and text.isupper()
                and len(text) <= 30
                and not any(c.isdigit() for c in text)
                and not ln.has_bullet
                and text.lower().strip().rstrip(":- ") not in self._HEADING_KEYWORDS
                and abs(ln.x0 - heading_x0) < 5
                and ln.top - heading_top < median_gap * 3
            ):
                # Check if heading title ends with hyphen (word break)
                if current_section.title.endswith("-"):
                    current_section.title = current_section.title + text
                else:
                    current_section.title += " " + text
                continue

            # ── Heading detection (multi-signal) ──
            if self._pdf_is_heading_multi(ln, body_size, median_gap):
                is_keyword_heading = self._text_contains_heading_keyword(
                    normalized
                )
                # Inside a known section (e.g. EXPERIENCE), only allow new sections
                # for lines that match heading keywords. Bold+gap company names
                # (e.g. "Shopee Dec 19 - Dec 21") fall through to role title.
                if is_keyword_heading or not inside_known_section:
                    # Use normalised title only for keyword headings
                    title = normalized if (is_spaced and is_keyword_heading) else text
                    current_section = Section(title=title, roles=[])
                    sections.append(current_section)
                    current_role = None
                    last_bullet = None
                    last_bullet_x0 = None
                    inside_known_section = is_keyword_heading
                    heading_x0 = ln.x0
                    heading_top = ln.top
                    continue
                # else: fall through to role title detection below

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

        # Signal 3: Known heading keyword (normalise spaced letters first)
        normalized = _normalize_spaced_heading(text)
        text_lower = normalized.lower().strip()
        text_clean = text_lower.rstrip(":- ")
        if self._text_contains_heading_keyword(text_clean):
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

