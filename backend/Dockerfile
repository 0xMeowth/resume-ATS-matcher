FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY config/ ./config/
COPY backend/ ./backend/

RUN uv sync --frozen --no-dev

# HuggingFace + sentence-transformers model cache (mounted as volume in compose)
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

EXPOSE 8000

CMD ["/bin/sh", "-c", "uv run uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
