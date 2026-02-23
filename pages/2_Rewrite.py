from __future__ import annotations

import base64
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ats_matcher.render.pdf_resume import render_resume_pdf
from ats_matcher.render.rewrite_utils import (
    compute_coverage,
    extract_resume_text,
    ordered_bullets_for_role,
    sanitize_editor_text,
)
from ats_matcher.models import ResumeData


st.set_page_config(page_title="Rewrite", layout="wide")
st.title("Rewrite")
st.caption(
    "Manual bullet editing with A4 PDF preview/export and term coverage tracking."
)
st.markdown(
    """
<style>
.rewrite-section h3 {
  margin-top: 0.2rem;
  margin-bottom: 0.1rem;
}
.rewrite-role {
  margin-top: 0.05rem;
  margin-bottom: 0.15rem;
  font-weight: 600;
  white-space: nowrap;
  overflow-x: auto;
}
</style>
""",
    unsafe_allow_html=True,
)

resume_data = st.session_state.get("resume_data")
if resume_data is None:
    st.warning("Upload and parse a resume on the main page first.")
    st.stop()
assert resume_data is not None
resume_data: ResumeData = cast(ResumeData, resume_data)


def _init_session_state() -> None:
    st.session_state.setdefault("resume_edits", {})
    st.session_state.setdefault("rewrite_pdf_bytes", b"")
    st.session_state.setdefault("coverage_prev", set())
    st.session_state.setdefault("coverage_now", set())
    st.session_state.setdefault("coverage_missing", [])
    st.session_state.setdefault("coverage_added", [])
    st.session_state.setdefault("coverage_removed", [])
    st.session_state.setdefault("coverage_history", [])
    st.session_state.setdefault("rewrite_name", "")
    st.session_state.setdefault("rewrite_contact", "")
    st.session_state.setdefault("rewrite_bullet_order", {})


def _role_key(section_idx: int, role_idx: int) -> str:
    return f"{section_idx}:{role_idx}"


def _ensure_order_map() -> None:
    existing = st.session_state.get("rewrite_bullet_order", {})
    updated = dict(existing)
    for section_idx, section in enumerate(resume_data.sections):
        for role_idx, role in enumerate(section.roles):
            key = _role_key(section_idx, role_idx)
            default_ids = [bullet.bullet_id for bullet in role.bullets]
            current_ids = updated.get(key, [])
            ordered = [
                bullet_id for bullet_id in current_ids if bullet_id in default_ids
            ]
            for bullet_id in default_ids:
                if bullet_id not in ordered:
                    ordered.append(bullet_id)
            updated[key] = ordered
    st.session_state["rewrite_bullet_order"] = updated


def _auto_tracked_terms() -> list[str]:
    terms = st.session_state.get("jd_skill_terms")
    if isinstance(terms, list) and terms:
        return [str(item).strip() for item in terms if str(item).strip()]

    matches = st.session_state.get("skill_matches")
    if not isinstance(matches, list):
        return []

    extracted: list[str] = []
    for match in matches:
        phrase = getattr(match, "phrase", "")
        if isinstance(phrase, str) and phrase.strip():
            extracted.append(phrase.strip())
    return extracted


def _effective_terms() -> list[str]:
    return _auto_tracked_terms()


def _sync_editor_to_edits(bullet_id: str) -> None:
    widget_key = f"rewrite_bullet_{bullet_id}"
    value = sanitize_editor_text(st.session_state.get(widget_key, ""))
    st.session_state[widget_key] = value
    edits = st.session_state.get("resume_edits", {}).copy()
    edits[bullet_id] = value
    st.session_state["resume_edits"] = edits
    _recompute_coverage_only()


def _move_bullet(role_key: str, bullet_id: str, step: int) -> None:
    order_map = st.session_state.get("rewrite_bullet_order", {}).copy()
    current = list(order_map.get(role_key, []))
    if bullet_id not in current:
        return
    idx = current.index(bullet_id)
    target = idx + step
    if target < 0 or target >= len(current):
        return
    current[idx], current[target] = current[target], current[idx]
    order_map[role_key] = current
    st.session_state["rewrite_bullet_order"] = order_map
    _recompute_coverage_only()
    st.rerun()


def _recompute_coverage_only() -> None:
    edits: dict[str, str] = st.session_state.get("resume_edits", {})
    order_map = st.session_state.get("rewrite_bullet_order", {})
    resume_text = extract_resume_text(
        resume=resume_data,
        edits=edits,
        bullet_order_by_role=order_map,
    )
    terms = _effective_terms()
    covered, missing = compute_coverage(terms=terms, resume_text=resume_text)

    covered_prev = set(st.session_state.get("coverage_now", set()))
    covered_now = set(covered)
    added = sorted(covered_now - covered_prev)
    removed = sorted(covered_prev - covered_now)

    st.session_state["coverage_prev"] = covered_prev
    st.session_state["coverage_now"] = covered_now
    st.session_state["coverage_added"] = added
    st.session_state["coverage_removed"] = removed
    st.session_state["coverage_missing"] = missing

    if added or removed:
        history = st.session_state.get("coverage_history", [])
        history.append(
            {
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "added": ", ".join(added),
                "removed": ", ".join(removed),
            }
        )
        st.session_state["coverage_history"] = history[-10:]


def _build_pdf_only() -> None:
    edits: dict[str, str] = st.session_state.get("resume_edits", {})
    order_map = st.session_state.get("rewrite_bullet_order", {})
    st.session_state["rewrite_pdf_bytes"] = render_resume_pdf(
        resume=resume_data,
        edits=edits,
        full_name=st.session_state.get("rewrite_name", ""),
        contact_line=st.session_state.get("rewrite_contact", ""),
        bullet_order_by_role=order_map,
    )


def _render_coverage_panel() -> None:
    st.subheader("Tracked Terms")
    auto_terms = _auto_tracked_terms()
    st.caption(f"Auto-loaded terms from JD analysis: {len(auto_terms)}")

    covered_now = sorted(st.session_state.get("coverage_now", set()))
    missing_now = st.session_state.get("coverage_missing", _effective_terms())

    col_cov, col_miss = st.columns(2, gap="small")
    with col_cov:
        st.markdown("**Covered**")
        _render_term_list(covered_now)
    with col_miss:
        st.markdown("**Missing**")
        _render_term_list(missing_now)

    added_terms = st.session_state.get("coverage_added", [])
    removed_terms = st.session_state.get("coverage_removed", [])
    if added_terms:
        st.success(f"Newly covered: {', '.join(added_terms)}")
    if removed_terms:
        st.error(f"Lost coverage: {', '.join(removed_terms)}")

    history = st.session_state.get("coverage_history", [])
    if history:
        with st.expander("Coverage history"):
            st.dataframe(pd.DataFrame(history), use_container_width=True)


def _render_editors() -> None:
    st.subheader("Manual Editing")
    st.text_input("Name", key="rewrite_name", placeholder="Your Name")
    st.text_input(
        "Contact line",
        key="rewrite_contact",
        placeholder="email | phone | city | linkedin",
    )

    order_map = st.session_state.get("rewrite_bullet_order", {})

    for section_idx, section in enumerate(resume_data.sections):
        st.markdown(
            f"<div class='rewrite-section'><h3>{section.title}</h3></div>",
            unsafe_allow_html=True,
        )
        for role_idx, role in enumerate(section.roles):
            if role.title:
                st.markdown(
                    f"<div class='rewrite-role'>{_format_role_header(role.title)}</div>",
                    unsafe_allow_html=True,
                )

            role_key = _role_key(section_idx, role_idx)
            ordered_bullets = ordered_bullets_for_role(
                role=role,
                role_key=role_key,
                bullet_order_by_role=order_map,
            )

            for bullet in ordered_bullets:
                widget_key = f"rewrite_bullet_{bullet.bullet_id}"
                if widget_key not in st.session_state:
                    initial = st.session_state["resume_edits"].get(
                        bullet.bullet_id,
                        bullet.text,
                    )
                    st.session_state[widget_key] = sanitize_editor_text(initial)

                current_text = sanitize_editor_text(
                    st.session_state.get(widget_key, "")
                )
                st.session_state[widget_key] = current_text
                editor_height = _editor_height(current_text)

                current_role_order = st.session_state.get(
                    "rewrite_bullet_order", {}
                ).get(role_key, [])
                bullet_idx = current_role_order.index(bullet.bullet_id)
                is_first = bullet_idx == 0
                is_last = bullet_idx == len(current_role_order) - 1

                controls_col, editor_box_col = st.columns(
                    [0.9, 10], gap="small", vertical_alignment="top"
                )
                with controls_col:
                    up_key = f"move_up_{role_key}_{bullet.bullet_id}"
                    if st.button(
                        "↑", key=up_key, disabled=is_first, use_container_width=True
                    ):
                        _move_bullet(
                            role_key=role_key, bullet_id=bullet.bullet_id, step=-1
                        )

                    down_key = f"move_down_{role_key}_{bullet.bullet_id}"
                    if st.button(
                        "↓",
                        key=down_key,
                        disabled=is_last,
                        use_container_width=True,
                    ):
                        _move_bullet(
                            role_key=role_key, bullet_id=bullet.bullet_id, step=1
                        )

                with editor_box_col:
                    st.text_area(
                        label=f"Bullet {bullet.bullet_id}",
                        key=widget_key,
                        height=editor_height,
                        label_visibility="collapsed",
                        on_change=_sync_editor_to_edits,
                        args=(bullet.bullet_id,),
                    )


def _editor_height(text: str) -> int:
    normalized = sanitize_editor_text(text)
    lines = normalized.splitlines() or [""]
    visual_lines = 0
    for line in lines:
        length = max(1, len(line))
        visual_lines += max(1, (length + 94) // 95)
    capped_lines = min(7, max(2, visual_lines))
    return 14 + capped_lines * 24


def _format_role_header(raw: str) -> str:
    compact = " ".join(raw.split())
    compact = re.sub(r"\s*\|\s*", " | ", compact)
    compact = re.sub(r"\s{2,}", " ", compact)
    compact = re.sub(r"\s*\|\s*", " | ", compact)
    compact = re.sub(r"\s{2,}", " ", compact)
    return compact


def _render_term_list(terms: list[str]) -> None:
    if not terms:
        st.caption("None")
        return
    st.markdown("\n".join(f"- {term}" for term in terms))


_init_session_state()
_ensure_order_map()

if not st.session_state.get("coverage_now") and not st.session_state.get(
    "coverage_missing"
):
    _recompute_coverage_only()

if not st.session_state.get("rewrite_pdf_bytes"):
    _build_pdf_only()

editor_col, coverage_col = st.columns([2.05, 0.95], gap="small")

with editor_col:
    with st.container(height=990):
        _render_editors()
    if st.button("Update preview", type="primary"):
        _build_pdf_only()
        st.success("PDF preview updated.")

with coverage_col:
    with st.container(border=True):
        _render_coverage_panel()
        st.caption(
            "Coverage panel remains visible while scrolling by using a scrollable editor pane "
            "on the left (closest reliable sticky behavior in Streamlit without custom frontend)."
        )

pdf_bytes = st.session_state.get("rewrite_pdf_bytes", b"")
if pdf_bytes:
    st.subheader("A4 PDF Preview")
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    iframe = (
        """
<div style="width:100%;height:900px;border:1px solid #ddd;">
  <iframe id="pdf-frame" style="width:100%;height:100%;border:none;" type="application/pdf"></iframe>
</div>
<script>
  const b64 = '"""
        + pdf_base64
        + """';
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    bytes[i] = raw.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const frame = document.getElementById('pdf-frame');
  if (frame) {
    frame.src = url;
  }
</script>
"""
    )
    components.html(iframe, height=920, scrolling=True)
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name="tailored_resume.pdf",
        mime="application/pdf",
    )
