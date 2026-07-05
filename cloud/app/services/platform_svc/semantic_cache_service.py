"""语义缓存服务提供基于语义相似度的缓存存取功能。"""

import math
import threading
from collections import OrderedDict

from cloud.app.services.agent_ops.ai_gateway_service import get_embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class SemanticCache:
    """语义缓存服务，基于嵌入向量的相似度计算实现缓存存取。"""

    def __init__(self, threshold: float = 0.92, max_entries: int = 1000):
        self.threshold = threshold
        self.max_entries = max_entries
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, query: str) -> dict | None:
        with self._lock:
            if query in self._cache:
                self._cache.move_to_end(query)
                return self._cache[query]["result"]

        query_embedding = get_embedding(query)
        if query_embedding is None:
            return None

        with self._lock:
            for key, value in self._cache.items():
                cached_emb = value["embedding"]
                if cached_emb is None:
                    continue
                sim = cosine_similarity(query_embedding, cached_emb)
                if sim > self.threshold:
                    self._cache.move_to_end(key)
                    return value["result"]

        return None

    def set(self, query: str, result: dict):
        embedding = get_embedding(query)
        if embedding is None:
            return

        with self._lock:
            if query in self._cache:
                self._cache.move_to_end(query)
                self._cache[query] = {"result": result, "embedding": embedding}
            else:
                self._cache[query] = {"result": result, "embedding": embedding}
                if len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)

    def __len__(self):
        with self._lock:
            return len(self._cache)
