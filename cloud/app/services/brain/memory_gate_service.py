"""记忆门控服务，集成门控仓库配置阈值与保留策略实现记忆筛选，条目仓库与全息服务提供持久化存储与语义关联，评估服务基于内容特征自动评分排序，支撑高效精准的记忆召回。"""

import json
from typing import Optional

from fastapi import Depends, HTTPException
from starlette import status

from cloud.app.database import get_db
from cloud.app.repositories import (
    MemoryEntriesRepository,
    MemoryGatesRepository,
    MemoryRecallLogRepository,
)
from cloud.app.services.brain.memory_evaluator_service import MemoryEvaluatorService
from cloud.app.services.compliance_svc.holographic_service import HolographicService
from shared.base_service import BaseService
from shared.datetime_utils import now as _now


class MemoryGateService(BaseService):
    """记忆门控服务，管理记忆条目的写入、筛选、召回与门控配置。"""

    def __init__(self, db=Depends(get_db), evaluator=None, dashboard_service=None, holographic_service=None, holographic_service_factory=None):
        """初始化 MemoryGateService。"""
        super().__init__(db)
        self._evaluator = evaluator
        self._dashboard_service = dashboard_service
        self._holographic_service = holographic_service
        self._holographic_service_factory = holographic_service_factory

    @property
    def evaluator(self):
        """获取 MemoryEvaluatorService 实例，按需延迟初始化。"""
        if self._evaluator is None:
            self._evaluator = MemoryEvaluatorService(self.db)
        return self._evaluator

    @property
    def dashboard_service(self):
        """获取仪表盘服务实例，默认为自身。"""
        if self._dashboard_service is None:
            self._dashboard_service = self
        return self._dashboard_service

    @property
    def holographic_service(self):
        """获取 HolographicService 实例，按需延迟初始化。"""
        if self._holographic_service is None:
            factory = self._holographic_service_factory or HolographicService
            self._holographic_service = factory(self.db)
        return self._holographic_service

    def create_gate(
        self, name: str, source_type: str, importance_threshold: float = 0.5, ttl_days: int = 90, retention_policy: str = "normal"
    ) -> dict:
        """创建记忆门控配置，指定阈值、TTL 与保留策略。"""
        repo = MemoryGatesRepository(self._connection())
        gate_id = repo.create(
            {
                "name": name,
                "source_type": source_type,
                "importance_threshold": importance_threshold,
                "ttl_days": ttl_days,
                "retention_policy": retention_policy,
                "created_at": _now(),
            }
        )
        return {
            "id": gate_id,
            "name": name,
            "source_type": source_type,
            "importance_threshold": importance_threshold,
            "ttl_days": ttl_days,
            "retention_policy": retention_policy,
        }

    def list_gates(self) -> list[dict]:
        """列出所有记忆门控配置。"""
        repo = MemoryGatesRepository(self._connection())
        return repo.list_ordered()

    def create_entry(
        self,
        title: str,
        content: str,
        memory_type: str,
        source_type: str,
        source_id: Optional[str],
        importance: float,
        context_tags: list[str],
        uid: int,
    ) -> dict:
        """创建记忆条目并触发全息自动关联。"""
        repo = MemoryEntriesRepository(self._connection())
        now = _now()
        tags = json.dumps(context_tags, ensure_ascii=False)
        entry_id = repo.create(
            {
                "title": title,
                "content": content,
                "memory_type": memory_type,
                "source_type": source_type,
                "source_id": source_id or "",
                "importance": importance,
                "context_tags": tags,
                "access_count": 0,
                "created_by": uid,
                "created_at": now,
                "updated_at": now,
            }
        )
        self.holographic_service.auto_associate(
            entry_id, {"context_tags": tags, "source_id": source_id or "", "memory_type": memory_type, "created_at": now}
        )
        return {
            "id": entry_id,
            "title": title,
            "content": content,
            "memory_type": memory_type,
            "source_type": source_type,
            "source_id": source_id,
            "importance": importance,
            "context_tags": context_tags,
        }

    def list_entries(
        self,
        memory_type: Optional[str] = None,
        importance_min: Optional[float] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, int, list[dict]]:
        """分页查询记忆条目，支持按类型、重要度和关键词筛选。"""
        repo = MemoryEntriesRepository(self._connection())
        return repo.list_filtered(memory_type=memory_type, importance_min=importance_min, keyword=keyword, page=page, page_size=page_size)

    def get_entry(self, entry_id: int) -> dict:
        """获取单条记忆条目详情并递增访问计数。"""
        repo = MemoryEntriesRepository(self._connection())
        row = repo.find_active_by_id(entry_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Entry not found")
        now = _now()
        repo.increment_access(entry_id, now)
        self.db.commit()
        return row

    def recall(self, query: str, memory_types: list[str], min_importance: float, max_results: int) -> dict:
        """按查询条件召回记忆条目，记录召回日志。"""
        entry_repo = MemoryEntriesRepository(self._connection())
        recall_repo = MemoryRecallLogRepository(self._connection())
        conditions, params = ["is_active = 1", "importance >= ?"], [min_importance]
        if memory_types:
            placeholders = ",".join("?" for _ in memory_types)
            conditions.append(f"memory_type IN ({placeholders})")
            params.extend(memory_types)
        where = " WHERE " + " AND ".join(conditions)
        rows = entry_repo.db.execute(
            f"SELECT id, title, content, memory_type, importance, context_tags FROM {entry_repo.table_name}{where} ORDER BY importance DESC LIMIT ?",
            params + [max_results],
        ).fetchall()
        results = [dict(r) for r in rows]
        ids = [r["id"] for r in rows]
        now = _now()
        recall_repo.create(
            {
                "query_text": query,
                "memory_ids": json.dumps(ids),
                "result_count": len(results),
                "context": json.dumps({"memory_types": memory_types}, ensure_ascii=False),
                "created_at": now,
            }
        )
        return {"results": results, "recall_count": len(results)}

    def auto_store(self, source_type: str, source_id: str, uid: int, auth_header: str = "") -> dict:
        """自动存储并评估指定源类型的记忆条目。"""
        return self.evaluator.auto_store(source_type=source_type, source_id=source_id, uid=uid, auth_header=auth_header)

    def dashboard(self) -> dict:
        """获取记忆系统仪表盘，包含总数、类型分布、热门标签与近期召回日志。"""
        entry_repo = MemoryEntriesRepository(self._connection())
        recall_repo = MemoryRecallLogRepository(self._connection())
        total = entry_repo.count_active()
        type_rows = entry_repo.by_type_stats()
        by_type = [{"memory_type": r["memory_type"], "count": r["cnt"], "avg_importance": round(r["avg_imp"], 4)} for r in type_rows]
        tag_counter = {}
        entries = entry_repo.all_context_tags_active()
        for e in entries:
            try:
                tags = json.loads(e["context_tags"])
            except (json.JSONDecodeError, TypeError):
                tags = []
            for tag in tags:
                tag_counter[tag] = tag_counter.get(tag, 0) + 1
        top_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        recent_logs = recall_repo.list_recent(limit=5)
        return {
            "total_entries": total,
            "by_memory_type": by_type,
            "top_context_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
            "recent_recall_logs": recent_logs,
        }
