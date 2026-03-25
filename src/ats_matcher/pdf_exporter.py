from __future__ import annotations

from typing import Any, List

import weasyprint


_RESUME_CSS = """\
@page {
    size: A4;
    margin: 1.8cm 2cm 1.8cm 2cm;
}

body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.4;
    color: #222;
    margin: 0;
}

h1.name {
    font-size: 16pt;
    margin: 0 0 2pt 0;
    text-transform: uppercase;
    letter-spacing: 1pt;
}

.contact {
    font-size: 9pt;
    color: #555;
    margin: 0 0 10pt 0;
}

.section-title {
    font-size: 11pt;
    font-weight: bold;
    text-transform: uppercase;
    border-bottom: 1px solid #333;
    padding-bottom: 2pt;
    margin: 12pt 0 6pt 0;
    letter-spacing: 0.5pt;
}

.role-title {
    font-weight: bold;
    font-size: 10pt;
    margin: 6pt 0 2pt 0;
}

ul.bullets {
    margin: 2pt 0 4pt 0;
    padding-left: 16pt;
}

ul.bullets li {
    margin-bottom: 2pt;
}
"""


def sections_to_html(sections: List[dict]) -> str:
    """Convert resume sections (frontend JSON shape) to styled HTML."""
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>"]
    parts.append(f"<style>{_RESUME_CSS}</style>")
    parts.append("</head><body>")

    for section in sections:
        title = section.get("title", "")
        roles = section.get("roles", [])

        # Header section (contact info) — title is the name
        if _is_header_section(section):
            parts.append(f'<h1 class="name">{_esc(title)}</h1>')
            contact_lines = []
            for role in roles:
                for bullet in role.get("bullets", []):
                    text = bullet.get("text", "").strip()
                    if text:
                        contact_lines.append(text)
            if contact_lines:
                parts.append(f'<p class="contact">{" | ".join(_esc(c) for c in contact_lines)}</p>')
            continue

        parts.append(f'<div class="section-title">{_esc(title)}</div>')
        for role in roles:
            role_title = role.get("title")
            if role_title:
                parts.append(f'<div class="role-title">{_esc(role_title)}</div>')
            bullets = role.get("bullets", [])
            if bullets:
                parts.append('<ul class="bullets">')
                for bullet in bullets:
                    text = bullet.get("text", "").strip()
                    if text:
                        parts.append(f"<li>{_esc(text)}</li>")
                parts.append("</ul>")

    parts.append("</body></html>")
    return "\n".join(parts)


def render_pdf(sections: List[dict]) -> bytes:
    """Render resume sections to PDF bytes via weasyprint."""
    html_str = sections_to_html(sections)
    doc = weasyprint.HTML(string=html_str)
    return doc.write_pdf()


def _is_header_section(section: dict) -> bool:
    """Detect header/contact section (first section, roles have no title)."""
    roles = section.get("roles", [])
    if not roles:
        return False
    return all(r.get("title") is None for r in roles)


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
