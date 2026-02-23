from __future__ import annotations

import base64
import sys
from datetime import UTC, datetime
from pathlib import Path

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
    split_newline_terms,
)


st.set_page_config(page_title="Rewrite", layout="wide")
st.title("Rewrite")
st.caption(
    "Manual bullet editing with A4 PDF preview/export and term coverage tracking."
)

resume_data = st.session_state.get("resume_data")
if resume_data is None:
    st.warning("Upload and parse a resume on the main page first.")
    st.stop()

st.session_state.setdefault("resume_edits", {})
st.session_state.setdefault("rewrite_pdf_bytes", b"")
st.session_state.setdefault("coverage_prev", set())
st.session_state.setdefault("coverage_now", set())
st.session_state.setdefault("coverage_added", [])
st.session_state.setdefault("coverage_removed", [])
st.session_state.setdefault("coverage_history", [])
st.session_state.setdefault("rewrite_name", "")
st.session_state.setdefault("rewrite_contact", "")
st.session_state.setdefault("rewrite_manual_terms", "")
st.session_state.setdefault("rewrite_use_manual_only", False)


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


def _build_pdf_and_coverage() -> None:
    edits: dict[str, str] = st.session_state.get("resume_edits", {})
    resume_text = extract_resume_text(resume_data, edits)
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

    st.session_state["rewrite_pdf_bytes"] = render_resume_pdf(
        resume=resume_data,
        edits=edits,
        full_name=st.session_state.get("rewrite_name", ""),
        contact_line=st.session_state.get("rewrite_contact", ""),
    )


with st.container(border=True):
    st.subheader("Tracked Terms")
    auto_terms = _auto_tracked_terms()
    st.caption(f"Auto-loaded terms from JD analysis: {len(auto_terms)}")

    st.text_area(
        "Manual term list (newline-separated)",
        key="rewrite_manual_terms",
        height=120,
        help="Use this to add terms or paste your own list.",
    )
    st.checkbox(
        "Use manual term list only",
        key="rewrite_use_manual_only",
        help="If checked, auto-loaded JD terms are ignored.",
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


with st.form("rewrite_editor_form"):
    st.subheader("Manual Editing")
    st.text_input("Name", key="rewrite_name", placeholder="Your Name")
    st.text_input(
        "Contact line",
        key="rewrite_contact",
        placeholder="email | phone | city | linkedin",
    )

    for section in resume_data.sections:
        st.markdown(f"### {section.title}")
        for role in section.roles:
            if role.title:
                st.markdown(f"**{role.title}**")
            for bullet in role.bullets:
                widget_key = f"rewrite_bullet_{bullet.bullet_id}"
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = st.session_state["resume_edits"].get(
                        bullet.bullet_id,
                        bullet.text,
                    )
                st.text_area(
                    label=f"Bullet {bullet.bullet_id}",
                    key=widget_key,
                    height=90,
                    label_visibility="collapsed",
                )

    update_preview = st.form_submit_button("Update preview")

if update_preview:
    edits = st.session_state.get("resume_edits", {}).copy()
    for section in resume_data.sections:
        for role in section.roles:
            for bullet in role.bullets:
                widget_key = f"rewrite_bullet_{bullet.bullet_id}"
                edits[bullet.bullet_id] = st.session_state.get(widget_key, bullet.text)
    st.session_state["resume_edits"] = edits
    _build_pdf_and_coverage()
    st.success("Preview and coverage updated.")

if not st.session_state.get("rewrite_pdf_bytes"):
    _build_pdf_and_coverage()

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
