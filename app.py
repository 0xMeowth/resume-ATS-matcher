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
from ats_matcher.phrase_ranker import rank_phrases_tfidf, select_phrases_mmr
from ats_matcher.resume_parser import ResumeParser
from ats_matcher.rewrite_engine import RewriteEngine


st.set_page_config(page_title="Resume ATS Matcher v0.1", layout="wide")


def clear_analysis_state() -> None:
    for key in [
        "skill_matches",
        "skill_extraction_debug",
        "rewrite_suggestions",
        "accepted_changes",
        "updated_docx",
    ]:
        st.session_state.pop(key, None)


def reset_session() -> None:
    for key in list(st.session_state.keys()):
        key_str = str(key)
        if key_str.startswith("resume_") or key_str.startswith("jd_"):
            del st.session_state[key]
    clear_analysis_state()
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    st.session_state["jd_url"] = ""
    st.session_state["jd_text"] = ""


st.title("Resume ATS Matcher v0.1")
st.caption("Human-in-the-loop resume tailoring from .docx resumes.")

with st.sidebar:
    st.header("Settings")
    st.markdown("**Skill term thresholds**")
    skill_strong_threshold = st.slider("Skill strong match", 0.5, 0.95, 0.7, 0.05)
    skill_weak_threshold = st.slider("Skill weak match", 0.3, 0.9, 0.55, 0.05)
    st.markdown("**Limits**")
    max_skill_terms = st.slider(
        "Max skill terms", 50, 200, 120, 10, on_change=clear_analysis_state
    )

    st.markdown("**Ranking strategy**")
    skill_ranker = st.selectbox(
        "Skill term ranking",
        ["MMR (embeddings)", "TF-IDF", "Hybrid (TF-IDF + MMR)"],
        on_change=clear_analysis_state,
    )
    mmr_diversity = None
    if skill_ranker in {"MMR (embeddings)", "Hybrid (TF-IDF + MMR)"}:
        mmr_diversity = st.slider(
            "MMR diversity", 0.0, 0.9, 0.3, 0.05, on_change=clear_analysis_state
        )

    st.markdown("**Matching strategy**")
    skill_matching = st.selectbox(
        "Skill matching",
        ["Embedding", "TF-IDF shortlist + Embedding"],
        on_change=clear_analysis_state,
    )
    rerank_top_k = None
    if skill_matching == "TF-IDF shortlist + Embedding":
        rerank_top_k = st.slider(
            "TF-IDF shortlist size", 5, 50, 15, 5, on_change=clear_analysis_state
        )

    st.markdown("**Debug**")
    debug_skill_extraction = st.checkbox(
        "Debug skill extraction",
        value=False,
        help="Logs keep/drop reasons to Streamlit Cloud logs and shows a debug table.",
    )

    if st.button("Reset session"):
        reset_session()
        st.rerun()


st.subheader("1) Upload resume (.docx)")
uploader_key = st.session_state.get("uploader_key", 0)
resume_file = st.file_uploader(
    "Resume (.docx)", type=["docx"], key=f"resume_upload_{uploader_key}"
)
if resume_file:
    resume_bytes = resume_file.getvalue()
    parser = ResumeParser()
    resume_data = parser.parse(resume_bytes)
    st.session_state["resume_data"] = resume_data
    st.session_state["resume_bytes"] = resume_bytes
    clear_analysis_state()

    st.success("Resume parsed")
    with st.expander("Parsed structure"):
        for section in resume_data.sections:
            st.markdown(f"**{section.title}**")
            for role in section.roles:
                st.write(role.title)
                for bullet in role.bullets:
                    st.write(f"- {bullet.text}")


st.subheader("2) Provide job description")
jd_url = st.text_input(
    "JD URL (optional)", key="jd_url", on_change=clear_analysis_state
)
jd_text = st.text_area(
    "JD text", height=200, key="jd_text", on_change=clear_analysis_state
)

if st.button("Analyze JD", disabled="resume_data" not in st.session_state):
    jd_parser = JDParser()
    raw_text = jd_parser.load_text(jd_text, jd_url)
    if not raw_text.strip():
        st.warning("Provide JD text or a valid URL before analyzing.")
        st.stop()
    extraction = jd_parser.extract_skill_components(
        raw_text,
        debug=debug_skill_extraction,
    )
    skill_candidates = extraction["combined_skills"]
    st.session_state["skill_extraction_debug"] = extraction.get("debug_events", [])

    resume_data = st.session_state["resume_data"]
    bullet_ids = list(resume_data.bullet_index.keys())
    bullet_texts = [resume_data.bullet_index[bid].text for bid in bullet_ids]

    embedding_engine = EmbeddingEngine()
    skill_embeddings = embedding_engine.embed(skill_candidates)
    doc_embedding = embedding_engine.embed([raw_text]).reshape(-1)
    if skill_ranker == "TF-IDF":
        selected_indices = rank_phrases_tfidf(
            phrases=skill_candidates,
            document=raw_text,
            max_phrases=max_skill_terms,
        )
    elif skill_ranker == "Hybrid (TF-IDF + MMR)":
        tfidf_indices = rank_phrases_tfidf(
            phrases=skill_candidates,
            document=raw_text,
            max_phrases=max_skill_terms * 3,
        )
        subset_phrases = [skill_candidates[i] for i in tfidf_indices]
        subset_embeddings = skill_embeddings[tfidf_indices]
        mmr_indices = select_phrases_mmr(
            phrases=subset_phrases,
            phrase_embeddings=subset_embeddings,
            doc_embedding=doc_embedding,
            max_phrases=max_skill_terms,
            diversity=mmr_diversity or 0.3,
        )
        selected_indices = [tfidf_indices[i] for i in mmr_indices]
    else:
        selected_indices = select_phrases_mmr(
            phrases=skill_candidates,
            phrase_embeddings=skill_embeddings,
            doc_embedding=doc_embedding,
            max_phrases=max_skill_terms,
            diversity=mmr_diversity or 0.3,
        )

    skill_terms = [skill_candidates[i] for i in selected_indices]
    skill_embeddings = skill_embeddings[selected_indices]
    bullet_embeddings = embedding_engine.embed(bullet_texts)

    matcher = MatchingEngine(
        skill_strong_threshold=skill_strong_threshold,
        skill_weak_threshold=skill_weak_threshold,
    )
    skill_matches = matcher.match_skill_terms(
        phrases=skill_terms,
        resume=resume_data,
        phrase_embeddings=skill_embeddings,
        bullet_embeddings=bullet_embeddings,
        bullet_ids=bullet_ids,
        matching_strategy="tfidf_rerank"
        if skill_matching == "TF-IDF shortlist + Embedding"
        else "embedding",
        rerank_top_k=rerank_top_k or 15,
    )

    st.session_state["jd_skill_terms"] = skill_terms
    st.session_state["skill_matches"] = skill_matches
    st.success("Analysis complete")


if "skill_matches" in st.session_state:
    st.subheader("3) Coverage report")

    st.markdown("**Skill coverage**")
    skill_matches = st.session_state["skill_matches"]
    skill_rows = []
    for match in skill_matches:
        skill_rows.append(
            {
                "skill_term": match.phrase,
                "match_type": match.match_type,
                "similarity": round(match.similarity, 3),
                "evidence": match.evidence_text or "",
            }
        )
    skill_df = pd.DataFrame(skill_rows)
    if not skill_df.empty:
        order = {
            "semantic_strong": 0,
            "semantic_weak": 1,
            "missing": 2,
            "exact": 3,
        }
        skill_df["_order"] = skill_df["match_type"].map(lambda x: order.get(x, 9))
        skill_df = skill_df.sort_values(by=["_order", "skill_term"]).drop(
            columns=["_order"]
        )
    st.dataframe(skill_df, use_container_width=True)

    exact_count = sum(1 for m in skill_matches if m.match_type == "exact")
    strong_count = sum(1 for m in skill_matches if m.match_type == "semantic_strong")
    weak_count = sum(1 for m in skill_matches if m.match_type == "semantic_weak")
    missing_count = sum(1 for m in skill_matches if m.match_type == "missing")
    st.write(
        "Exact: "
        f"{exact_count} | Strong semantic: {strong_count} | Weak semantic: {weak_count} | "
        f"Missing: {missing_count}"
    )

    debug_events = st.session_state.get("skill_extraction_debug", [])
    if debug_events:
        with st.expander("Skill extraction debug"):
            debug_view = st.radio(
                "Debug view",
                ["Actionable drops", "Full trace"],
                horizontal=True,
            )
            debug_df = pd.DataFrame(debug_events)
            if debug_view == "Actionable drops":
                debug_df = debug_df[
                    (debug_df["action"] == "dropped")
                    & (debug_df["source"] != "single_token")
                ]
            st.dataframe(debug_df, use_container_width=True)

    if st.button("Generate rewrite suggestions"):
        rewrite_engine = RewriteEngine()
        suggestions = rewrite_engine.generate(
            skill_matches, st.session_state["resume_data"]
        )
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
