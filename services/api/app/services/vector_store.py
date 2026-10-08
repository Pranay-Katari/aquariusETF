"""Small, deterministic Chroma retrieval layer for the basket research agent."""

from functools import lru_cache
import hashlib
import re

from ..config import settings
from .market import CATALOG


def _embed(text: str, dimensions: int = 256) -> list[float]:
    """Dependency-free hashed embedding; keeps retrieval private and repeatable."""
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]{2,}", text.lower()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % dimensions
        vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


@lru_cache(maxsize=1)
def _collection():
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        collection = client.get_or_create_collection("instrument-research", metadata={"hnsw:space": "cosine"})
        documents, ids, embeddings = [], [], []
        for ticker, (name, tag, url, description) in CATALOG.items():
            document = f"{ticker} {name}. Theme: {tag}. {description} Source: {url}"
            ids.append(f"instrument:{ticker}")
            documents.append(document)
            embeddings.append(_embed(document))
        collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=[{"ticker": ticker} for ticker in CATALOG])
        return collection
    except Exception:
        return None


def retrieve(query: str, limit: int = 6) -> list[str]:
    collection = _collection()
    if collection is None or not query.strip():
        return []
    try:
        result = collection.query(query_embeddings=[_embed(query)], n_results=limit, include=["documents"])
        return [document for document in result.get("documents", [[]])[0] if document]
    except Exception:
        return []
