FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY config/ ./config/
COPY backend/ ./backend/
COPY db/ ./db/

RUN uv sync --frozen --no-dev && uv pip install --no-deps -e .

# HuggingFace + sentence-transformers model cache (mounted as volume in compose)
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

# Pre-download models so cold starts don't hit HuggingFace at request time
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

CMD ["/bin/sh", "-c", "uv run uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
