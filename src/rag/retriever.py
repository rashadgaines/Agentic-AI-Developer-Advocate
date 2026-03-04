"""
Queries the FAISS index to retrieve relevant RC doc chunks for a given query.
"""

import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path("data/index")
MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 5

_model: SentenceTransformer | None = None
_index: faiss.Index | None = None
_chunks: list[str] = []
_metadata: list[dict] = []


def _load() -> None:
    global _model, _index, _chunks, _metadata

    if _model is not None:
        return

    index_path = INDEX_DIR / "rc_docs.faiss"
    chunks_path = INDEX_DIR / "chunks.pkl"
    metadata_path = INDEX_DIR / "metadata.pkl"

    if not index_path.exists():
        raise FileNotFoundError(
            "FAISS index not found. Run `python -m src.cli ingest` first."
        )

    _model = SentenceTransformer(MODEL_NAME)
    _index = faiss.read_index(str(index_path))
    with open(chunks_path, "rb") as f:
        _chunks = pickle.load(f)
    with open(metadata_path, "rb") as f:
        _metadata = pickle.load(f)


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Returns top_k relevant chunks for a query.
    Each result: {"chunk": str, "url": str, "title": str, "score": float}
    """
    _load()

    query_vec = _model.encode([query]).astype("float32")
    faiss.normalize_L2(query_vec)

    scores, indices = _index.search(query_vec, top_k)

    results = []
    seen_urls = set()
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        meta = _metadata[idx]
        results.append({
            "chunk": _chunks[idx],
            "url": meta["url"],
            "title": meta["title"],
            "score": float(score),
        })
        seen_urls.add(meta["url"])

    return results


def format_context(results: list[dict]) -> str:
    """Format retrieved chunks into a prompt-ready context block."""
    if not results:
        return "No relevant documentation found."

    parts = []
    for r in results:
        parts.append(
            f"[SOURCE: {r['title']} — {r['url']}]\n{r['chunk']}"
        )
    return "\n\n---\n\n".join(parts)
