from __future__ import annotations

import sys
from typing import Dict

sys.path.append("src")

import pandas as pd
import streamlit as st

from ats_matcher.embedding_engine import EmbeddingEngine
from ats_matcher.exporter import Exporter
from ats_matcher.jd_parser import JDParser
from ats_matcher.matching_engine import MatchingEngine
from ats_matcher.phrase_ranker import select_phrases_mmr
from ats_matcher.resume_parser import ResumeParser
from ats_matcher.rewrite_engine import RewriteEngine


st.set_page_config(page_title="Resume ATS Matcher v0.1", layout="wide")


def reset_state() -> None:
    for key in list(st.session_state.keys()):
        if (
            key.startswith("resume_")
            or key.startswith("jd_")
            or key.startswith("match_")
        ):
            del st.session_state[key]


st.title("Resume ATS Matcher v0.1")
st.caption("Human-in-the-loop resume tailoring from .docx resumes.")

with st.sidebar:
    st.header("Settings")
    semantic_threshold = st.slider("Semantic match threshold", 0.4, 0.9, 0.6, 0.05)
    max_phrases = st.slider("Max JD phrases", 50, 200, 120, 10)
    if st.button("Reset session"):
        reset_state()
        st.rerun()


st.subheader("1) Upload resume (.docx)")
resume_file = st.file_uploader("Resume (.docx)", type=["docx"], key="resume_upload")
if resume_file:
    resume_bytes = resume_file.getvalue()
    parser = ResumeParser()
    resume_data = parser.parse(resume_bytes)
    st.session_state["resume_data"] = resume_data
    st.session_state["resume_bytes"] = resume_bytes

    st.success("Resume parsed")
    with st.expander("Parsed structure"):
        for section in resume_data.sections:
            st.markdown(f"**{section.title}**")
            for role in section.roles:
                st.write(role.title)
                for bullet in role.bullets:
                    st.write(f"- {bullet.text}")


st.subheader("2) Provide job description")
jd_url = st.text_input("JD URL (optional)")
jd_text = st.text_area("JD text", height=200)

if st.button("Analyze JD", disabled="resume_data" not in st.session_state):
    jd_parser = JDParser(max_phrases=max_phrases)
    raw_text = jd_parser.load_text(jd_text, jd_url)
    if not raw_text.strip():
        st.warning("Provide JD text or a valid URL before analyzing.")
        st.stop()
    phrase_candidates = jd_parser.extract_phrases(raw_text)

    resume_data = st.session_state["resume_data"]
    bullet_ids = list(resume_data.bullet_index.keys())
    bullet_texts = [resume_data.bullet_index[bid].text for bid in bullet_ids]

    embedding_engine = EmbeddingEngine()
    phrase_embeddings = embedding_engine.embed(phrase_candidates)
    doc_embedding = embedding_engine.embed([raw_text]).reshape(-1)
    selected_indices = select_phrases_mmr(
        phrases=phrase_candidates,
        phrase_embeddings=phrase_embeddings,
        doc_embedding=doc_embedding,
        max_phrases=max_phrases,
    )
    phrases = [phrase_candidates[i] for i in selected_indices]
    phrase_embeddings = phrase_embeddings[selected_indices]
    bullet_embeddings = embedding_engine.embed(bullet_texts)

    matcher = MatchingEngine(semantic_threshold=semantic_threshold)
    matches = matcher.match_phrases(
        phrases=phrases,
        resume=resume_data,
        phrase_embeddings=phrase_embeddings,
        bullet_embeddings=bullet_embeddings,
        bullet_ids=bullet_ids,
    )

    st.session_state["jd_phrases"] = phrases
    st.session_state["match_results"] = matches
    st.success("Analysis complete")


if "match_results" in st.session_state:
    st.subheader("3) Coverage report")
    matches = st.session_state["match_results"]
    rows = []
    for match in matches:
        rows.append(
            {
                "phrase": match.phrase,
                "match_type": match.match_type,
                "similarity": round(match.similarity, 3),
                "evidence": match.evidence_text or "",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    exact_count = sum(1 for m in matches if m.match_type == "exact")
    semantic_count = sum(1 for m in matches if m.match_type == "semantic")
    missing_count = sum(1 for m in matches if m.match_type == "missing")
    st.write(
        f"Exact: {exact_count} | Semantic: {semantic_count} | Missing: {missing_count}"
    )

    if st.button("Generate rewrite suggestions"):
        rewrite_engine = RewriteEngine()
        suggestions = rewrite_engine.generate(matches, st.session_state["resume_data"])
        st.session_state["rewrite_suggestions"] = suggestions


if "rewrite_suggestions" in st.session_state:
    st.subheader("4) Review and accept edits")
    resume_data = st.session_state["resume_data"]
    accepted_changes: Dict[str, str] = st.session_state.get("accepted_changes", {})

    if not st.session_state["rewrite_suggestions"]:
        st.info("No suggestions generated for the current JD.")

    for idx, suggestion in enumerate(st.session_state["rewrite_suggestions"]):
        bullet = resume_data.bullet_index.get(suggestion.bullet_id)
        if not bullet:
            continue
        with st.expander(f"Bullet {idx + 1}: {bullet.text[:80]}"):
            st.write(f"Suggested keyword: {suggestion.phrase}")
            st.write(suggestion.suggestion_text)
            edited = st.text_area(
                "Edit bullet text",
                value=bullet.text,
                key=f"edit_{suggestion.bullet_id}",
                height=100,
            )
            accept = st.checkbox(
                "Accept this change", key=f"accept_{suggestion.bullet_id}"
            )
            if accept:
                accepted_changes[suggestion.bullet_id] = edited
            elif suggestion.bullet_id in accepted_changes:
                del accepted_changes[suggestion.bullet_id]

    st.session_state["accepted_changes"] = accepted_changes

    if accepted_changes:
        st.success(f"Ready to apply {len(accepted_changes)} changes")

    if st.button("Apply accepted changes"):
        exporter = Exporter()
        updated_docx = exporter.apply_changes(
            st.session_state["resume_bytes"],
            st.session_state["resume_data"],
            accepted_changes,
        )
        st.session_state["updated_docx"] = updated_docx
        st.success("Changes applied")


if "updated_docx" in st.session_state:
    st.subheader("5) Export tailored resume")
    st.download_button(
        "Download tailored .docx",
        data=st.session_state["updated_docx"],
        file_name="tailored_resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
