from __future__ import annotations

from io import BytesIO
from typing import List, Optional

from docx import Document

from ats_matcher.models import Bullet, ResumeData, Role, Section
from ats_matcher.utils import stable_bullet_id

# PDF magic bytes: %PDF
_PDF_MAGIC = b"%PDF"


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

        for idx, paragraph in enumerate(document.paragraphs):
            text = paragraph.text.strip()
            if not text:
                continue

            style_name = paragraph.style.name if paragraph.style else ""

            if self._is_heading(style_name, text):
                current_section = Section(title=text, roles=[])
                sections.append(current_section)
                current_role = None
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
                continue

            if current_section is None:
                current_section = Section(title="General", roles=[])
                sections.append(current_section)

            current_role = Role(title=text, bullets=[])
            current_section.roles.append(current_role)

        return ResumeData(sections=sections, bullet_index=bullet_index)

    # ── PDF ─────────────────────────────────────────────────────────────────

    def _parse_pdf(self, pdf_bytes: bytes) -> ResumeData:
        import pdfplumber

        lines: List[str] = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines())

        sections: List[Section] = []
        bullet_index = {}

        current_section: Optional[Section] = None
        current_role: Optional[Role] = None
        bullet_counter = 0

        for idx, raw_line in enumerate(lines):
            text = raw_line.strip()
            if not text:
                continue

            if self._pdf_is_heading(text):
                current_section = Section(title=text, roles=[])
                sections.append(current_section)
                current_role = None
                continue

            if self._pdf_is_bullet(text):
                # Strip common bullet markers
                text = text.lstrip("-•·▪▸►✓* ").strip()
                if not text:
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
                    text=text,
                    paragraph_index=idx,
                    section_title=current_section.title,
                    role_title=current_role.title,
                )
                current_role.bullets.append(bullet)
                bullet_index[bullet_id] = bullet
                continue

            if current_section is None:
                current_section = Section(title="General", roles=[])
                sections.append(current_section)

            current_role = Role(title=text, bullets=[])
            current_section.roles.append(current_role)

        return ResumeData(
            sections=sections, bullet_index=bullet_index, low_confidence=True
        )

    # ── Helpers (DOCX) ───────────────────────────────────────────────────────

    def _is_heading(self, style_name: str, text: str) -> bool:
        if style_name.lower().startswith("heading"):
            return True
        if text.isupper() and len(text) <= 40:
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

    # ── Helpers (PDF) ────────────────────────────────────────────────────────

    def _pdf_is_heading(self, text: str) -> bool:
        if text.isupper() and len(text) <= 40:
            return True
        return False

    def _pdf_is_bullet(self, text: str) -> bool:
        if text[:1] in "-•·▪▸►✓*":
            return True
        return False
