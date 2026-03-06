# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# System deps for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && \
    rm -rf /var/lib/apt/lists/*

# Install uv (fast package installer)
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./

# Install only runtime deps (no dev), skip tensorlake (replaced by pymupdf)
RUN uv pip install --system --no-cache \
    fastapi "uvicorn[standard]" python-multipart \
    python-dotenv pydantic requests \
    crewai crewai-tools \
    openai voyageai "zep-crewai" firecrawl-py \
    chromadb pymupdf \
    --only-binary :all:


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin/uvicorn    /usr/local/bin/uvicorn

# Copy application source
COPY backend.py         ./
COPY frontend/          ./frontend/
COPY src/               ./src/

# Create writable dirs for vector DB and uploads
RUN mkdir -p chroma_db uploads && \
    chown -R appuser:appuser /app

USER appuser

# Expose FastAPI port
EXPOSE 8000

# Health-check so Docker/K8s knows the app is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status')" || exit 1

# Start the server
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
