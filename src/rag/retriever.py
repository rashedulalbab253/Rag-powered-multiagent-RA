"""
ChromaDB-based vector store (replaces milvus-lite which has no Windows binary wheel).
Drop-in replacement: same insert() / search() / get_collection_count() API.
"""
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings


class MilvusVectorDB:
    """
    Wraps ChromaDB with the exact same interface that was written against MilvusClient
    so no other files need changing.
    """

    def __init__(self, db_path: str = "chroma_db", collection_name: str = "research_assistant"):
        self.collection_name = collection_name
        # Persistent local storage
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        # Always get-or-create (safe for restarts)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    def insert(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]] = None,
    ):
        assert len(chunks) == len(embeddings), "Mismatch between chunks and embeddings"

        ids = [f"{self.collection_name}_{self.get_collection_count() + i}" for i in range(len(chunks))]
        metas = []
        for i in range(len(chunks)):
            m = metadata[i] if metadata and i < len(metadata) else {}
            metas.append({
                "page_number": int(m.get("page_number", 0)),
                "chunk_index": int(m.get("chunk_index", i)),
                "source_file": str(m.get("source_file", "unknown")),
            })

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metas,
        )

    # ------------------------------------------------------------------
    def get_collection_count(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0

    # ------------------------------------------------------------------
    def search(
        self,
        query_embedding: List[float],
        limit: int = 3,
        **_kwargs,
    ) -> List[Dict[str, Any]]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, max(self.get_collection_count(), 1)),
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "score": 1.0 - dist,  # cosine distance → similarity
                "page_number": meta.get("page_number", 0),
                "chunk_index": meta.get("chunk_index", 0),
                "source_file": meta.get("source_file", "unknown"),
            })

        return hits