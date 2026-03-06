# Single-stage build — simpler, no multi-stage gRPC issues
FROM python:3.13-slim

# System deps needed by chromadb and pymupdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libglib2.0-0 libgl1 && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# ── Install in layers (each layer cached independently) ──────────────────────

# Layer 1 — web framework (tiny, changes most often)
RUN pip install --no-cache-dir \
    "fastapi==0.135.1" \
    "uvicorn[standard]==0.41.0" \
    "python-multipart==0.0.22" \
    "python-dotenv==1.1.1" \
    "pydantic==2.11.10" \
    "requests>=2.32"

# Layer 2 — LLM / embedding clients
RUN pip install --no-cache-dir \
    "openai==2.26.0" \
    "voyageai==0.3.7" \
    "firecrawl-py==4.18.0"

# Layer 3 — Memory
RUN pip install --no-cache-dir \
    "zep-crewai==1.1.1"

# Layer 4 — CrewAI (largest, slowest)
RUN pip install --no-cache-dir \
    "crewai==1.10.1" \
    "crewai-tools==1.10.1"

# Layer 5 — RAG stack (ChromaDB + PyMuPDF)
RUN pip install --no-cache-dir \
    "chromadb==1.1.1" \
    "pymupdf==1.26.7"

# ── Copy application source ───────────────────────────────────────────────────
COPY backend.py     ./
COPY frontend/      ./frontend/
COPY src/           ./src/

# Writable dirs
RUN mkdir -p chroma_db uploads && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEMO_MODE=false

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status')" || exit 1

CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
