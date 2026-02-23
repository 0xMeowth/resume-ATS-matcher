from __future__ import annotations

import base64
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
    split_newline_terms,
)
from ats_matcher.models import ResumeData


st.set_page_config(page_title="Rewrite", layout="wide")
st.title("Rewrite")
st.caption(
    "Manual bullet editing with A4 PDF preview/export and term coverage tracking."
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
    st.session_state.setdefault("rewrite_manual_terms", "")
    st.session_state.setdefault("rewrite_use_manual_only", False)
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
    auto_terms = _auto_tracked_terms()
    manual_terms = split_newline_terms(st.session_state.get("rewrite_manual_terms", ""))

    if st.session_state.get("rewrite_use_manual_only", False):
        return manual_terms

    merged: list[str] = []
    seen: set[str] = set()
    for term in auto_terms + manual_terms:
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        merged.append(term)
    return merged


def _sync_editor_to_edits(bullet_id: str) -> None:
    widget_key = f"rewrite_bullet_{bullet_id}"
    value = sanitize_editor_text(st.session_state.get(widget_key, ""))
    st.session_state[widget_key] = value
    edits = st.session_state.get("resume_edits", {}).copy()
    edits[bullet_id] = value
    st.session_state["resume_edits"] = edits
    _recompute_coverage_only()


def _on_terms_change() -> None:
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

    st.text_area(
        "Manual term list (newline-separated)",
        key="rewrite_manual_terms",
        height=120,
        help="Use this to add terms or paste your own list.",
        on_change=_on_terms_change,
    )
    st.checkbox(
        "Use manual term list only",
        key="rewrite_use_manual_only",
        help="If checked, auto-loaded JD terms are ignored.",
        on_change=_on_terms_change,
    )

    covered_now = sorted(st.session_state.get("coverage_now", set()))
    missing_now = st.session_state.get("coverage_missing", _effective_terms())

    col_cov, col_miss = st.columns(2)
    with col_cov:
        st.markdown("**Covered**")
        st.write(covered_now or "None")
    with col_miss:
        st.markdown("**Missing**")
        st.write(missing_now or "None")

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
        st.markdown(f"### {section.title}")
        for role_idx, role in enumerate(section.roles):
            if role.title:
                st.markdown(f"**{role.title}**")

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

                left, middle, right = st.columns(
                    [0.8, 0.8, 10], vertical_alignment="top"
                )
                with left:
                    st.markdown("↕")
                    up_key = f"move_up_{role_key}_{bullet.bullet_id}"
                    if st.button("↑", key=up_key):
                        _move_bullet(
                            role_key=role_key, bullet_id=bullet.bullet_id, step=-1
                        )
                with middle:
                    down_key = f"move_down_{role_key}_{bullet.bullet_id}"
                    if st.button("↓", key=down_key):
                        _move_bullet(
                            role_key=role_key, bullet_id=bullet.bullet_id, step=1
                        )
                with right:
                    st.text_area(
                        label=f"Bullet {bullet.bullet_id}",
                        key=widget_key,
                        height=90,
                        label_visibility="collapsed",
                        on_change=_sync_editor_to_edits,
                        args=(bullet.bullet_id,),
                    )


_init_session_state()
_ensure_order_map()

if not st.session_state.get("coverage_now") and not st.session_state.get(
    "coverage_missing"
):
    _recompute_coverage_only()

if not st.session_state.get("rewrite_pdf_bytes"):
    _build_pdf_only()

st.markdown(
    """
<style>
div[data-testid="column"]:nth-of-type(2) > div {
    position: sticky;
    top: 0.75rem;
}
</style>
""",
    unsafe_allow_html=True,
)

editor_col, coverage_col = st.columns([1.9, 1.1], gap="large")

with editor_col:
    _render_editors()
    if st.button("Update preview", type="primary"):
        _build_pdf_only()
        st.success("PDF preview updated.")

with coverage_col:
    with st.container(border=True):
        _render_coverage_panel()
        st.caption(
            "Coverage panel is sticky in this column. If browser/CSP blocks sticky behavior, "
            "it remains visible as a dedicated right column while you scroll."
        )

pdf_bytes = st.session_state.get("rewrite_pdf_bytes", b"")
if pdf_bytes:
    st.subheader("A4 PDF Preview")
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    iframe = (
        "<iframe "
        'src="data:application/pdf;base64,'
        + pdf_base64
        + '" width="100%" height="900" type="application/pdf"></iframe>'
    )
    components.html(iframe, height=920, scrolling=True)
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name="tailored_resume.pdf",
        mime="application/pdf",
    )
