from __future__ import annotations

from contextlib import asynccontextmanager

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
    yield


app = FastAPI(title="Resume ATS Matcher API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
