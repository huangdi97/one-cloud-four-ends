"""复合评分记忆门 — 支持 semantic/recency/importance 评分 + scope tree 自组织。"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from cloud.app.agent_runtime.memory.vector_memory import VectorMemory


@dataclass
class MemoryEntry:
    content: str
    scope: str = "default"
    importance: float = 0.5
    timestamp: float = 0.0
    embedding: list[float] | None = None


class ScoredMemory:
    SEMANTIC_WEIGHT = 0.5
    RECENCY_WEIGHT = 0.3
    IMPORTANCE_WEIGHT = 0.2

    def __init__(self, vector_memory: VectorMemory | None = None):
        self._entries: list[MemoryEntry] = []
        self._short_term: list[MemoryEntry] = []
        self._long_term: list[MemoryEntry] = []
        self._vector = vector_memory or VectorMemory()

    def remember(self, content: str, scope: str | None = None) -> str:
        """记忆一条内容，自动推断 scope 和 importance。"""
        resolved_scope = scope or self._infer_scope(content)
        importance = self._infer_importance(content)
        entry = MemoryEntry(
            content=content,
            scope=resolved_scope,
            importance=importance,
            timestamp=time.time(),
        )
        self._entries.append(entry)
        self._short_term.append(entry)
        self._vector.store("_scored_memory_", content, content, metadata={"scope": resolved_scope, "importance": importance})
        return resolved_scope

    def recall(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """按组合评分召回最相关的记忆。"""
        query_emb = self._embed(query)
        now = time.time()
        age_range = max(now - min((e.timestamp for e in self._entries), default=now), 1.0)

        scored = []
        for e in self._entries:
            semantic = self._cosine_similarity(query_emb, self._embed(e.content)) if e.embedding else 0.0
            recency = 1.0 - (now - e.timestamp) / age_range
            importance = e.importance
            composite = semantic * self.SEMANTIC_WEIGHT + recency * self.RECENCY_WEIGHT + importance * self.IMPORTANCE_WEIGHT
            scored.append((composite, e))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"content": e.content, "scope": e.scope, "importance": e.importance, "score": round(s, 4)} for s, e in scored[:top_k]]

    def tree(self) -> dict[str, int]:
        """返回 scope 分布统计树。"""
        scope_counts: dict[str, int] = defaultdict(int)
        for e in self._entries:
            scope_counts[e.scope] += 1
        return dict(sorted(scope_counts.items()))

    def forget(self, scope: str, threshold: float = 0.3) -> int:
        """删除指定 scope 中低于重要性阈值的记忆。"""
        before = len(self._entries)
        self._entries = [e for e in self._entries if not (e.scope == scope and e.importance < threshold)]
        self._short_term = [e for e in self._short_term if not (e.scope == scope and e.importance < threshold)]
        return before - len(self._entries)

    def consolidate(self) -> dict[str, int]:
        """将高重要性短期记忆提升到长期存储。"""
        promoted = 0
        for e in list(self._short_term):
            if e.importance >= 0.7:
                self._long_term.append(e)
                self._short_term.remove(e)
                promoted += 1
        return {"promoted": promoted, "short_term": len(self._short_term), "long_term": len(self._long_term)}

    def _infer_scope(self, content: str) -> str:
        keywords = {
            "compliance": ["合规", "compliance", "violation", "违规", "审计", "audit"],
            "visit": ["拜访", "visit", "hcp", "医生"],
            "competitor": ["竞品", "competitor", "竞争对手", "market"],
            "expense": ["费用", "expense", "报销", "差旅"],
            "opportunity": ["机会", "opportunity", "商机", "pipeline"],
        }
        content_lower = content.lower()
        for scope, kws in keywords.items():
            if any(kw in content_lower for kw in kws):
                return scope
        return "general"

    def _infer_importance(self, content: str) -> float:
        high_signals = ["urgent", "紧急", "critical", "关键", "violation", "违规", "compliance", "合规"]
        low_signals = ["日常", "routine", "一般", "normal"]
        content_lower = content.lower()
        if any(s in content_lower for s in high_signals):
            return 0.9
        if any(s in content_lower for s in low_signals):
            return 0.3
        return 0.5

    def _embed(self, text: str) -> list[float]:
        try:
            return self._vector._get_embedding(text)
        except Exception:
            return [0.0] * 384

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        return dot
