import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from threading import Lock


class VectorCache:
    def __init__(self, threshold: float = 0.97, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)
        self._threshold = threshold
        self._index = faiss.IndexFlatIP(384)  # Inner product on L2-normalized = cosine similarity
        self._values: list[str] = []
        self._lock = Lock()

    def _encode(self, text: str) -> np.ndarray:
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec.astype("float32")

    def get(self, query: str) -> str | None:
        with self._lock:
            if self._index.ntotal == 0:
                return None
            vec = self._encode(query)
            distances, indices = self._index.search(vec, 1)
            score = float(distances[0][0])
            if score >= self._threshold:
                return self._values[int(indices[0][0])]
            return None

    def set(self, query: str, value: str) -> None:
        with self._lock:
            vec = self._encode(query)
            self._index.add(vec)
            self._values.append(value)
