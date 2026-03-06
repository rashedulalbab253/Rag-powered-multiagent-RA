# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Layer 1: Core web framework (small, changes rarely) ──────────────────────
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi "uvicorn[standard]" python-multipart \
    python-dotenv pydantic requests

# ── Layer 2: AI / LLM packages (large but changes rarely) ────────────────────
RUN pip install --no-cache-dir \
    openai voyageai firecrawl-py

# ── Layer 3: Memory (zep) ────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
    "zep-crewai"

# ── Layer 4: CrewAI core ─────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
    crewai crewai-tools

# ── Layer 5: Vector DB + PDF parser ─────────────────────────────────────────
RUN pip install --no-cache-dir \
    chromadb pymupdf


# ── Stage 2: Slim runtime ────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY backend.py     ./
COPY frontend/      ./frontend/
COPY src/           ./src/

# Writable dirs for vector DB and uploads
RUN mkdir -p chroma_db uploads && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status')" || exit 1

CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
