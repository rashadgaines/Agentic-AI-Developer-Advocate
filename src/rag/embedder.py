"""
Chunks scraped RC docs and builds a FAISS vector index using sentence-transformers.
"""

import json
import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

DOCS_DIR = Path("data/docs")
INDEX_DIR = Path("data/index")
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500      # tokens (approximated by words)
CHUNK_OVERLAP = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def load_docs() -> list[dict]:
    """Load all scraped JSON docs."""
    docs = []
    for path in DOCS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            if data.get("content"):
                docs.append(data)
        except Exception:
            pass
    return docs


def build_index() -> None:
    """Build and persist FAISS index from scraped docs."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    docs = load_docs()
    if not docs:
        print("No docs found in data/docs/. Run `python -m src.cli ingest` first.")
        return

    print(f"Chunking {len(docs)} documents...")
    chunks = []
    metadata = []

    for doc in docs:
        doc_chunks = chunk_text(doc["content"])
        for chunk in doc_chunks:
            chunks.append(chunk)
            metadata.append({"url": doc["url"], "title": doc["title"]})

    print(f"Embedding {len(chunks)} chunks...")
    embeddings = model.encode(chunks, show_progress_bar=True, batch_size=64)
    embeddings = np.array(embeddings).astype("float32")

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    # Build flat inner-product index (cosine after normalization)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # Persist
    faiss.write_index(index, str(INDEX_DIR / "rc_docs.faiss"))
    with open(INDEX_DIR / "chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)
    with open(INDEX_DIR / "metadata.pkl", "wb") as f:
        pickle.dump(metadata, f)

    print(f"\nIndex built: {len(chunks)} chunks, dim={dim}")
    print(f"Saved to {INDEX_DIR}/")


if __name__ == "__main__":
    build_index()
