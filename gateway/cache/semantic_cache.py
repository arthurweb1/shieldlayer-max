from __future__ import annotations

import hashlib
import os
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class SemanticCache:
    def __init__(self, dim: int, threshold: float, index_path: str) -> None:
        self._dim = dim
        self._threshold = threshold
        self._index_path = index_path
        self._store: dict[int, tuple[str, str]] = {}
        self._next_id = 0
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

        if os.path.exists(index_path):
            self._index = faiss.read_index(index_path)
            store_path = index_path + ".store"
            if os.path.exists(store_path):
                with open(store_path, "rb") as fh:
                    saved = pickle.load(fh)
                    self._store = saved.get("store", {})
                    self._next_id = saved.get("next_id", 0)
        else:
            self._index = faiss.IndexFlatIP(self._dim)

    async def lookup(self, prompt: str) -> str | None:
        if self._index.ntotal == 0:
            return None

        vec = self._encode(prompt)
        distances, indices = self._index.search(vec, 1)

        similarity = float(distances[0][0])
        faiss_id = int(indices[0][0])

        if similarity >= self._threshold and faiss_id in self._store:
            return self._store[faiss_id][1]

        return None

    async def store(self, prompt: str, response: str) -> None:
        vec = self._encode(prompt)
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

        self._index.add(vec)
        self._store[self._next_id] = (prompt_hash, response)
        self._next_id += 1

        self._persist()

    def _encode(self, text: str) -> np.ndarray:
        embedding = self._model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return embedding.astype(np.float32)

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._index_path) or ".", exist_ok=True)
        faiss.write_index(self._index, self._index_path)
        store_path = self._index_path + ".store"
        with open(store_path, "wb") as fh:
            pickle.dump({"store": self._store, "next_id": self._next_id}, fh)
