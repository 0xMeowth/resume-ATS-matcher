from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ats_matcher.embedding_engine import EmbeddingEngine
from ats_matcher.jd_parser import JDParser
from backend.routers import router
from db.connection import get_connection
from db.migrate import apply_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure DB schema exists before serving requests
    conn = get_connection()
    apply_schema(conn)
    conn.close()

    app.state.jd_parser = JDParser()
    app.state.embedding_engine = EmbeddingEngine()
    app.state.resume_store = {}
    app.state.analysis_store = {}

    if os.environ.get("USE_CROSS_ENCODER") == "1":
        from sentence_transformers import CrossEncoder
        app.state.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    else:
        app.state.cross_encoder = None

    yield


app = FastAPI(title="Resume ATS Matcher API", version="0.1.0", lifespan=lifespan)

_frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
