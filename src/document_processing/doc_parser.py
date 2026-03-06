"""
PyMuPDF-based document parser (replaces tensorlake which requires Rust/maturin to build).
Drop-in replacement: same upload() / parse_structured() / get_result() API.
Uses PyMuPDF (fitz) which has a pre-built Windows binary wheel.
"""
import os
import json
from typing import Iterable, List, Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

import fitz  # PyMuPDF


load_dotenv()

# ---------------------------------------------------------------------------
# Schema kept for API compatibility (not used in parsing but imported by rag_pipeline)
# ---------------------------------------------------------------------------
RESEARCH_PAPER_SCHEMA = {
    "type": "object",
    "properties": {
        "paper": {
            "type": "object",
            "properties": {
                "title":      {"type": "string"},
                "authors":    {"type": "array", "items": {"type": "string"}},
                "abstract":   {"type": "string"},
                "keywords":   {"type": "array", "items": {"type": "string"}},
                "key_findings": {"type": "array", "items": {"type": "string"}},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["heading", "summary"],
                    },
                },
            },
            "required": ["title", "authors", "abstract", "sections"],
        }
    },
    "required": ["paper"],
}


# ---------------------------------------------------------------------------
# Tiny stub classes so rag_pipeline.py's result.chunks / result.model_dump()
# still work without changes.
# ---------------------------------------------------------------------------
@dataclass
class Chunk:
    content: str
    page_number: int


@dataclass
class ParseResult:
    chunks: List[Chunk] = field(default_factory=list)
    structured: Dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, Any]:
        return {
            "chunks": [{"content": c.content, "page_number": c.page_number} for c in self.chunks],
            "structured": self.structured,
        }


# ---------------------------------------------------------------------------
# Main client (same public interface as the original TensorLakeClient)
# ---------------------------------------------------------------------------
class TensorLakeClient:
    """
    Local PDF parser that uses PyMuPDF instead of the TensorLake cloud API.
    The chunk size is ~500 chars to stay similar to the original chunking strategy.
    """

    CHUNK_SIZE = 500   # characters

    def __init__(self, api_key: Optional[str] = None):
        # api_key kept for signature compatibility; not used
        pass

    # --- internal helpers --------------------------------------------------

    def _split_text(self, text: str) -> List[str]:
        """Simple character-level chunking with sentence boundary preference."""
        chunks, start = [], 0
        while start < len(text):
            end = min(start + self.CHUNK_SIZE, len(text))
            # Prefer splitting at sentence end
            for sep in (".\n", ". ", ".\t", "\n\n"):
                pos = text.rfind(sep, start, end)
                if pos > start + self.CHUNK_SIZE // 2:
                    end = pos + len(sep)
                    break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end
        return chunks

    # --- public interface (mirrors TensorLakeClient) -----------------------

    def upload(self, paths: Iterable[str]) -> List[str]:
        """
        'Upload' just validates that the files exist and returns their paths as IDs.
        No network call needed.
        """
        ids = []
        for path in paths:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            if os.path.getsize(path) == 0:
                raise ValueError(f"File is empty: {path}")
            ids.append(path)   # path is the "file ID"
        return ids

    def parse_structured(
        self,
        file_id: str,
        json_schema: Dict[str, Any],
        *,
        page_range=None,
        labels=None,
        **_kwargs,
    ) -> str:
        """
        Returns file_id as the parse_id (we parse synchronously in get_result).
        """
        return file_id   # parse_id == path

    def get_result(self, parse_id: str) -> ParseResult:
        """
        Actually parse the PDF using PyMuPDF and return a ParseResult.
        """
        path = parse_id
        doc = fitz.open(path)
        chunks: List[Chunk] = []

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            for chunk_text in self._split_text(text):
                chunks.append(Chunk(content=chunk_text, page_number=page_num))

        doc.close()

        if not chunks:
            raise RuntimeError(f"No text could be extracted from '{path}'")

        # Build minimal structured metadata from first page
        first_page_text = chunks[0].content if chunks else ""
        structured = {
            "paper": {
                "title":    first_page_text[:120].split("\n")[0].strip(),
                "authors":  [],
                "abstract": first_page_text[:500],
                "keywords": [],
                "key_findings": [],
                "sections": [{"heading": f"Page {c.page_number}", "summary": c.content[:200]} for c in chunks[:5]],
            }
        }

        return ParseResult(chunks=chunks, structured=structured)

    # Compatibility stubs (called nowhere in the new code path but kept to avoid import errors)
    def list_uploaded_files(self):
        return []

    def verify_file_uploaded(self, file_id: str) -> bool:
        return os.path.exists(file_id)
