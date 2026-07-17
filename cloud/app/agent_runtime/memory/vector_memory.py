"""轻量级向量记忆，用于 Agent 的语义检索。"""

import json
import logging
import os
import sqlite3
import struct
import sys
from datetime import datetime

logger = logging.getLogger(__name__)


class VectorMemory:
    """轻量级向量记忆，用于 Agent 的语义检索。使用 sentence-transformers 嵌入 + SQLite 存储。"""

    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "data",
            "agent_vector_memory.db",
        )
        self._model = None
        self._local_db = None
        self._external_db = None
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        if self._external_db is not None:
            return self._external_db
        if self._local_db is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._local_db = sqlite3.connect(self.db_path)
            self._local_db.row_factory = sqlite3.Row
        return self._local_db

    def set_db(self, db):
        """设置外部数据库连接覆盖默认路径。"""
        self._external_db = db
        self._ensure_table()

    def _ensure_table(self):
        try:
            conn = self._get_connection()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS agent_vector_memory ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "agent_name TEXT NOT NULL, "
                "key TEXT NOT NULL, "
                "content TEXT NOT NULL, "
                "embedding BLOB, "
                "metadata TEXT DEFAULT '{}', "
                "shared_with TEXT DEFAULT '[]', "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "UNIQUE(agent_name, key)"
                ")"
            )
            try:
                conn.execute("ALTER TABLE agent_vector_memory ADD COLUMN shared_with TEXT DEFAULT '[]'")
            except Exception as e:
                logger.warning("ALTER TABLE shared_with failed: %s", e)
            # FTS5 全文搜索虚拟表
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS agent_vector_memory_fts "
                    "USING fts5(agent_name, key, content, content=agent_vector_memory, content_rowid=id)"
                )
            except Exception:
                logger.warning("FTS5 table creation failed (not available or already exists)", exc_info=True)
            conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to ensure vector memory table")

    def _get_model(self):
        if self._model is None:
            try:
                _user_site = os.path.expanduser("~/.local/lib/python3.12/site-packages")
                if _user_site not in sys.path:
                    sys.path.insert(0, _user_site)
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.EMBEDDING_MODEL)
            except ImportError:
                logger.warning("sentence-transformers not installed, using fallback embedding")
                self._model = None
        return self._model

    def _get_embedding(self, text: str) -> list[float]:
        """生成文本的嵌入向量。若 embedding 模型不可用（未安装），则返回全零向量（384维）作为降级策略。
        降级后的全零向量将导致语义搜索退化为随机排序——调用方需自行检测此情况并告警。"""
        model = self._get_model()
        if model is not None:
            return model.encode(text, normalize_embeddings=True).tolist()
        return [0.0] * 384

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        return struct.pack(f"{len(embedding)}f", *embedding)

    def _deserialize_embedding(self, blob: bytes) -> list[float]:
        return list(struct.unpack(f"{len(blob) // 4}f", blob))

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        return dot

    def store(self, agent_name: str, key: str, content: str, metadata: dict = None, share_with: list[str] | None = None):
        """存储向量记忆条目，支持跨Agent共享。

        Args:
            agent_name: 所属Agent名称
            key: 记忆键
            content: 记忆内容
            metadata: 元数据
            share_with: 共享给哪些Agent读，["*"] 表示全部，None 表示不共享
        """
        embedding = self._get_embedding(content)
        conn = self._get_connection()
        shared_json = json.dumps(share_with or [], ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO agent_vector_memory "
            "(agent_name, key, content, embedding, metadata, shared_with, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                agent_name,
                key,
                content,
                self._serialize_embedding(embedding),
                json.dumps(metadata or {}, ensure_ascii=False),
                shared_json,
                datetime.now().isoformat(),
            ),
        )
        # 同步更新 FTS 索引
        try:
            row_id = conn.execute(
                "SELECT id FROM agent_vector_memory WHERE agent_name=? AND key=?",
                (agent_name, key),
            ).fetchone()
            if row_id:
                conn.execute(
                    "INSERT OR REPLACE INTO agent_vector_memory_fts (rowid, agent_name, key, content) VALUES (?, ?, ?, ?)",
                    (row_id["id"], agent_name, key, content),
                )
        except Exception as e:
            logger.warning("FTS sync failed: %s", e)
        conn.commit()

    def search(self, agent_name: str, query: str, top_k: int = 5, cross_agent: bool = True) -> list[dict]:
        """语义搜索向量记忆，支持跨Agent共享记忆查询。

        Args:
            agent_name: 查询的Agent名称
            query: 查询文本
            top_k: 返回条数
            cross_agent: 是否搜索其他Agent共享的记忆
        """
        query_emb = self._get_embedding(query)
        conn = self._get_connection()
        if cross_agent:
            rows = conn.execute(
                "SELECT key, content, metadata, shared_with, agent_name, created_at, embedding "
                "FROM agent_vector_memory WHERE agent_name=? "
                "OR shared_with='[\"*\"]' OR shared_with LIKE ?",
                (agent_name, f'%"{agent_name}"%'),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key, content, metadata, shared_with, agent_name, created_at, embedding FROM agent_vector_memory WHERE agent_name=?",
                (agent_name,),
            ).fetchall()
        scored = []
        for row in rows:
            stored_emb = self._deserialize_embedding(row["embedding"]) if row["embedding"] else [0.0] * 384
            score = self._cosine_similarity(query_emb, stored_emb)
            source_agent = row["agent_name"]
            scored.append(
                (
                    score,
                    {
                        "key": row["key"],
                        "content": row["content"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                        "source_agent": source_agent,
                        "created_at": row["created_at"],
                        "score": round(score, 4),
                    },
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def hybrid_search(self, agent_name: str, query: str, top_k: int = 5, cross_agent: bool = True, alpha: float = 0.3) -> list[dict]:
        """混合检索：关键词(FTS5) + 向量语义融合，按组合得分排序。

        Alpha控制权重：0=纯向量，1=纯关键词，0.3=默认偏向语义。
        """
        # --- 向量检索 ---
        query_emb = self._get_embedding(query)
        conn = self._get_connection()
        if cross_agent:
            rows = conn.execute(
                "SELECT id, key, content, metadata, shared_with, agent_name, created_at, embedding "
                "FROM agent_vector_memory WHERE agent_name=? "
                "OR shared_with='[\"*\"]' OR shared_with LIKE ?",
                (agent_name, f'%"{agent_name}"%'),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, key, content, metadata, shared_with, agent_name, created_at, embedding FROM agent_vector_memory WHERE agent_name=?",
                (agent_name,),
            ).fetchall()

        vector_scores = {}
        for row in rows:
            stored_emb = self._deserialize_embedding(row["embedding"]) if row["embedding"] else [0.0] * 384
            score = self._cosine_similarity(query_emb, stored_emb)
            vector_scores[row["id"]] = {
                "key": row["key"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "source_agent": row["agent_name"],
                "created_at": row["created_at"],
                "vec_score": score,
            }

        if not vector_scores:
            return []

        # --- 关键词检索 (FTS5) ---
        keyword_scores = {}
        try:
            fts_rows = conn.execute(
                "SELECT rowid, rank FROM agent_vector_memory_fts WHERE content MATCH ? ORDER BY rank LIMIT ?",
                (query, top_k * 3),
            ).fetchall()
            for fts_row in fts_rows:
                keyword_scores[fts_row["rowid"]] = -fts_row["rank"]  # FTS5 rank 负数=更相关
        except Exception:
            pass  # FTS not available, fall back to pure vector

        # --- 分数归一化与融合 ---
        def _minmax(scores_dict, key):
            vals = [v[key] for v in scores_dict.values()]
            if not vals:
                return {}
            mn, mx = min(vals), max(vals)
            rng = mx - mn if mx > mn else 1.0
            return {rid: (v[key] - mn) / rng for rid, v in scores_dict.items()}

        vec_norm = _minmax(vector_scores, "vec_score")
        kw_norm = {}
        if keyword_scores:
            kw_vals = list(keyword_scores.values())
            kw_min, kw_max = min(kw_vals), max(kw_vals)
            kw_rng = kw_max - kw_min if kw_max > kw_min else 1.0
            kw_norm = {rid: (kw - kw_min) / kw_rng for rid, kw in keyword_scores.items()}

        all_ids = set(vector_scores.keys()) | set(kw_norm.keys())
        scored = []
        for rid in all_ids:
            vs = vec_norm.get(rid, 0.0)
            ks = kw_norm.get(rid, 0.0)
            combined = alpha * ks + (1.0 - alpha) * vs
            entry = dict(vector_scores.get(rid, {}))
            if rid in keyword_scores:
                entry["keyword_score"] = round(keyword_scores.get(rid, 0), 4)
            entry["vec_score"] = round(vector_scores.get(rid, {}).get("vec_score", 0), 4)
            entry["score"] = round(combined, 4)
            scored.append((combined, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def recall(self, agent_name: str, key: str, cross_agent: bool = True) -> str | None:
        """按 key 精确召回向量记忆内容，本agent查不到时查共享记忆。"""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT content FROM agent_vector_memory WHERE agent_name=? AND key=?",
            (agent_name, key),
        ).fetchone()
        if row:
            return row["content"]
        if cross_agent:
            row = conn.execute(
                "SELECT content FROM agent_vector_memory WHERE key=? AND (shared_with='[\"*\"]' OR shared_with LIKE ?)",
                (key, f'%"{agent_name}"%'),
            ).fetchone()
            if row:
                return row["content"]
        return None
