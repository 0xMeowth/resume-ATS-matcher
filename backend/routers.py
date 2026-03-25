from __future__ import annotations

from typing import Literal, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ats_matcher.models import PhraseMatch, ResumeData
from ats_matcher.pdf_exporter import render_pdf
from db.writer import log_feedback
from ats_matcher.matching_engine import MatchingEngine
from ats_matcher.phrase_ranker import rank_phrases_tfidf, select_phrases_mmr
from ats_matcher.resume_parser import ResumeParser
from ats_matcher.rewrite_engine import RewriteEngine
from backend.stores import AnalysisEntry, ResumeEntry, new_id

router = APIRouter()

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ── Schemas ───────────────────────────────────────────────────────────────────

class BulletOut(BaseModel):
    bullet_id: str
    text: str


class RoleOut(BaseModel):
    title: str | None
    bullets: list[BulletOut]


class SectionOut(BaseModel):
    title: str
    roles: list[RoleOut]


class ResumeUploadResponse(BaseModel):
    resume_id: str
    low_confidence: bool
    sections: list[SectionOut]


class AnalyzeSettings(BaseModel):
    max_skill_terms: int = 120
    skill_ranker: Literal["mmr", "tfidf", "hybrid"] = "mmr"
    mmr_diversity: float = 0.3
    skill_matching: Literal["embedding", "tfidf_rerank"] = "embedding"
    rerank_top_k: int = 15
    skill_strong_threshold: float = 0.7
    skill_weak_threshold: float = 0.55
    debug: bool = False
    whitelist_only: bool = False


class AnalyzeRequest(BaseModel):
    resume_id: str
    jd_text: str | None = None
    jd_url: str | None = None
    settings: AnalyzeSettings = Field(default_factory=AnalyzeSettings)


class PhraseMatchOut(BaseModel):
    phrase: str
    match_type: str
    similarity: float
    evidence_bullet_id: str | None
    evidence_text: str | None


class InjectionHintOut(BaseModel):
    bullet_id: str
    score: float


class AnalyzeResponse(BaseModel):
    analysis_id: str
    skill_matches: list[PhraseMatchOut]
    injection_hints: dict[str, dict[str, InjectionHintOut]] = Field(default_factory=dict)
    debug_events: list[dict] | None = None


class BulletIn(BaseModel):
    bullet_id: str = ""
    text: str


class RoleIn(BaseModel):
    title: str | None = None
    bullets: list[BulletIn]


class SectionIn(BaseModel):
    title: str
    roles: list[RoleIn]


class PdfExportRequest(BaseModel):
    sections: list[SectionIn]


class FeedbackRequest(BaseModel):
    analysis_id: str
    skill_phrase: str
    bullet_text: Optional[str] = None
    label: str  # 'covered' or 'not_covered'


class RewriteSuggestRequest(BaseModel):
    analysis_id: str
    phrase: str
    bullet_text: str


class RewriteSuggestResponse(BaseModel):
    suggested_text: str


class EmbedRoleRequest(BaseModel):
    analysis_id: str
    phrase: str
    bullets: list[BulletIn]


class EmbedRoleResponse(BaseModel):
    bullet_id: str
    score: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_injection_hints(
    skill_matches: list[PhraseMatch],
    skill_terms: list[str],
    skill_embeddings: np.ndarray,
    bullet_embeddings: np.ndarray,
    bullet_ids: list[str],
    resume_data: ResumeData,
) -> dict[str, dict[str, dict]]:
    """For each missing keyword, find the best bullet per role (dot product = cosine, embeddings are L2-normalised)."""
    if bullet_embeddings.size == 0:
        return {}
    bullet_role: dict[str, tuple[int, int]] = {}
    for si, section in enumerate(resume_data.sections):
        for ri, role in enumerate(section.roles):
            for bullet in role.bullets:
                bullet_role[bullet.bullet_id] = (si, ri)
    phrase_to_idx = {p: i for i, p in enumerate(skill_terms)}
    hints: dict[str, dict[str, dict]] = {}
    for match in skill_matches:
        if match.match_type != "missing":
            continue
        idx = phrase_to_idx.get(match.phrase)
        if idx is None:
            continue
        phrase_vec = skill_embeddings[idx : idx + 1]
        sims = np.dot(bullet_embeddings, phrase_vec.T).reshape(-1)
        role_best: dict[str, tuple[str, float]] = {}
        for i, bid in enumerate(bullet_ids):
            rk = bullet_role.get(bid)
            if rk is None:
                continue
            key = f"{rk[0]}-{rk[1]}"
            score = float(sims[i])
            if key not in role_best or score > role_best[key][1]:
                role_best[key] = (bid, score)
        hints[match.phrase] = {
            k: {"bullet_id": bid, "score": sc}
            for k, (bid, sc) in role_best.items()
        }
    return hints


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok"}


# ── Resume upload ─────────────────────────────────────────────────────────────

@router.post("/resume", response_model=ResumeUploadResponse)
async def upload_resume(request: Request, file: UploadFile):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        resume_data = ResumeParser().parse(file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")

    resume_id = new_id()
    request.app.state.resume_store[resume_id] = ResumeEntry(
        file_bytes=file_bytes,
        resume_data=resume_data,
        filename=file.filename or "resume",
    )

    return ResumeUploadResponse(
        resume_id=resume_id,
        low_confidence=resume_data.low_confidence,
        sections=[
            SectionOut(
                title=section.title,
                roles=[
                    RoleOut(
                        title=role.title,
                        bullets=[
                            BulletOut(bullet_id=b.bullet_id, text=b.text)
                            for b in role.bullets
                        ],
                    )
                    for role in section.roles
                ],
            )
            for section in resume_data.sections
        ],
    )


# ── JD analyze ────────────────────────────────────────────────────────────────

@router.post("/jd/analyze", response_model=AnalyzeResponse)
async def analyze_jd(body: AnalyzeRequest, request: Request):
    resume_entry = request.app.state.resume_store.get(body.resume_id)
    if resume_entry is None:
        raise HTTPException(status_code=404, detail="resume_id not found")

    if not (body.jd_text or "").strip() and not (body.jd_url or "").strip():
        raise HTTPException(status_code=400, detail="Provide jd_text or jd_url")

    cfg = body.settings
    jd_parser = request.app.state.jd_parser
    embedding_engine = request.app.state.embedding_engine
    resume_data = resume_entry.resume_data

    raw_text = jd_parser.load_text(body.jd_text, body.jd_url)
    extraction = jd_parser.extract_skill_components(raw_text, debug=cfg.debug, whitelist_only=cfg.whitelist_only)
    skill_candidates = extraction["combined_skills"]
    debug_events = extraction.get("debug_events")

    bullet_ids = list(resume_data.bullet_index.keys())
    bullet_texts = [resume_data.bullet_index[bid].text for bid in bullet_ids]

    skill_embeddings = embedding_engine.embed(skill_candidates, prefix=BGE_QUERY_PREFIX)
    doc_embedding = embedding_engine.embed([raw_text], prefix=BGE_QUERY_PREFIX).reshape(-1)

    if cfg.skill_ranker == "tfidf":
        selected_indices = rank_phrases_tfidf(
            phrases=skill_candidates,
            document=raw_text,
            max_phrases=cfg.max_skill_terms,
        )
    elif cfg.skill_ranker == "hybrid":
        tfidf_indices = rank_phrases_tfidf(
            phrases=skill_candidates,
            document=raw_text,
            max_phrases=cfg.max_skill_terms * 3,
        )
        subset_phrases = [skill_candidates[i] for i in tfidf_indices]
        subset_embeddings = skill_embeddings[tfidf_indices]
        mmr_indices = select_phrases_mmr(
            phrases=subset_phrases,
            phrase_embeddings=subset_embeddings,
            doc_embedding=doc_embedding,
            max_phrases=cfg.max_skill_terms,
            diversity=cfg.mmr_diversity,
        )
        selected_indices = [tfidf_indices[i] for i in mmr_indices]
    else:  # mmr (default)
        selected_indices = select_phrases_mmr(
            phrases=skill_candidates,
            phrase_embeddings=skill_embeddings,
            doc_embedding=doc_embedding,
            max_phrases=cfg.max_skill_terms,
            diversity=cfg.mmr_diversity,
        )

    skill_terms = [skill_candidates[i] for i in selected_indices]
    skill_embeddings = skill_embeddings[selected_indices]
    bullet_embeddings = embedding_engine.embed(bullet_texts)

    matcher = MatchingEngine(
        skill_strong_threshold=cfg.skill_strong_threshold,
        skill_weak_threshold=cfg.skill_weak_threshold,
        cross_encoder=getattr(request.app.state, "cross_encoder", None),
    )
    skill_matches = matcher.match_skill_terms(
        phrases=skill_terms,
        resume=resume_data,
        phrase_embeddings=skill_embeddings,
        bullet_embeddings=bullet_embeddings,
        bullet_ids=bullet_ids,
        matching_strategy="tfidf_rerank" if cfg.skill_matching == "tfidf_rerank" else "embedding",
        rerank_top_k=cfg.rerank_top_k,
    )

    injection_hints = _compute_injection_hints(
        skill_matches=skill_matches,
        skill_terms=skill_terms,
        skill_embeddings=skill_embeddings,
        bullet_embeddings=bullet_embeddings,
        bullet_ids=bullet_ids,
        resume_data=resume_data,
    )

    analysis_id = new_id()
    request.app.state.analysis_store[analysis_id] = AnalysisEntry(
        resume_id=body.resume_id,
        jd_text=raw_text,
        jd_url=body.jd_url,
        skill_matches=skill_matches,
        doc_embedding=doc_embedding,
        injection_hints=injection_hints,
    )

    return AnalyzeResponse(
        analysis_id=analysis_id,
        skill_matches=[
            PhraseMatchOut(
                phrase=m.phrase,
                match_type=m.match_type,
                similarity=m.similarity,
                evidence_bullet_id=m.evidence_bullet_id,
                evidence_text=m.evidence_text,
            )
            for m in skill_matches
        ],
        injection_hints={
            phrase: {
                rk: InjectionHintOut(bullet_id=v["bullet_id"], score=v["score"])
                for rk, v in role_hints.items()
            }
            for phrase, role_hints in injection_hints.items()
        },
        debug_events=debug_events,
    )


# ── PDF Export ────────────────────────────────────────────────────────────────

@router.post("/export/pdf")
def export_pdf(body: PdfExportRequest):
    sections_dicts = [s.model_dump() for s in body.sections]
    try:
        pdf_bytes = render_pdf(sections_dicts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="tailored_resume.pdf"'},
    )


# ── Feedback ──────────────────────────────────────────────────────────────────

@router.post("/feedback", status_code=204)
def submit_feedback(body: FeedbackRequest):
    log_feedback(body.analysis_id, body.skill_phrase, body.bullet_text, body.label)
    return Response(status_code=204)


# ── Rewrite ───────────────────────────────────────────────────────────────────

@router.post("/rewrite/suggest", response_model=RewriteSuggestResponse)
async def rewrite_suggest(body: RewriteSuggestRequest, request: Request):
    if request.app.state.analysis_store.get(body.analysis_id) is None:
        raise HTTPException(status_code=404, detail="analysis_id not found")
    suggested = await RewriteEngine().suggest_single(body.bullet_text, body.phrase)
    return RewriteSuggestResponse(suggested_text=suggested)


@router.post("/rewrite/embed-role", response_model=EmbedRoleResponse)
async def embed_role(body: EmbedRoleRequest, request: Request):
    if request.app.state.analysis_store.get(body.analysis_id) is None:
        raise HTTPException(status_code=404, detail="analysis_id not found")
    if not body.bullets:
        raise HTTPException(status_code=400, detail="bullets required")
    embedding_engine = request.app.state.embedding_engine
    phrase_vec = embedding_engine.embed([body.phrase], prefix=BGE_QUERY_PREFIX)[0]
    bullet_vecs = embedding_engine.embed([b.text for b in body.bullets])
    sims = np.dot(bullet_vecs, phrase_vec).reshape(-1)
    best_idx = int(np.argmax(sims))
    return EmbedRoleResponse(
        bullet_id=body.bullets[best_idx].bullet_id,
        score=float(sims[best_idx]),
    )
