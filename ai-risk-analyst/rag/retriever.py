"""
Phase 6: RAG Layer.
Retrieves relevant fraud-pattern knowledge for a given transaction/risk context,
so the LLM's explanation is grounded in real documented patterns instead of
reasoning purely from the numbers.

Uses TF-IDF vectors + FAISS instead of a full embedding model (sentence-transformers)
to keep install size/time small. Same retrieve() interface either way -- swap the
internals later if you want true semantic embeddings.
"""

import os
import re
import numpy as np
import faiss
from sklearn.feature_extraction.text import TfidfVectorizer

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "fraud_knowledge.txt")

_vectorizer = None
_index = None
_docs = []  # list of {"id": str, "title": str, "content": str}


def _load_docs():
    with open(DATA_PATH, "r") as f:
        raw = f.read()

    # Each doc starts with "[ID] Title" on its own line
    blocks = re.split(r"\n(?=\[)", raw.strip())
    docs = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        header, _, body = block.partition("\n")
        match = re.match(r"\[(.+?)\]\s*(.*)", header)
        if not match:
            continue
        doc_id, title = match.group(1), match.group(2)
        docs.append({"id": doc_id, "title": title, "content": body.strip()})
    return docs


def build_index():
    """Loads docs, fits TF-IDF, builds a FAISS index. Called once at app startup."""
    global _vectorizer, _index, _docs
    _docs = _load_docs()
    texts = [f"{d['title']}. {d['content']}" for d in _docs]

    _vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = _vectorizer.fit_transform(texts).toarray().astype("float32")

    dimension = tfidf_matrix.shape[1]
    _index = faiss.IndexFlatL2(dimension)
    _index.add(tfidf_matrix)


def retrieve(query: str, top_k: int = 2) -> list[dict]:
    """Returns the top_k most relevant knowledge chunks for the given query string."""
    if _index is None:
        build_index()

    query_vec = _vectorizer.transform([query]).toarray().astype("float32")
    distances, indices = _index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(_docs):
            continue
        results.append({**_docs[idx], "distance": float(dist)})
    return results