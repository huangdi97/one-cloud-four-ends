"""记忆评估服务，负责 AI 评分与 auto_store 逻辑。"""

import json
import logging

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import (
    ComplianceAuditRecordsRepository,
    CrossCaseInsightsRepository,
    DecisionCasesRepository,
    MemoryEntriesRepository,
    MemoryGatesRepository,
)
from cloud.app.services.compliance_svc.holographic_service import HolographicService
from shared.datetime_utils import now as _now

logger = logging.getLogger(__name__)


class MemoryEvaluatorService:
    def __init__(self, db, ai_gateway=None, holographic_service=None, holographic_service_factory=None):
        """初始化记忆评估服务。

        参数:
            db: 数据库连接
            ai_gateway: 可选，AI 网关服务实例
            holographic_service: 可选，全息服务实例
            holographic_service_factory: 可选，全息服务工厂类
        """
        self.db = db
        self._ai_gateway = ai_gateway
        self._holographic_service = holographic_service
        self._holographic_service_factory = holographic_service_factory

    @property
    def ai_gateway(self):
        """获取 AI 网关服务实例（惰性初始化）。"""
        if self._ai_gateway is None:
            from cloud.app.services.agent_ops.ai_gateway_service import AiGatewayService

            self._ai_gateway = AiGatewayService(self.db)
        return self._ai_gateway

    @property
    def holographic_service(self):
        """获取全息服务实例（惰性初始化）。"""
        if self._holographic_service is None:
            factory = self._holographic_service_factory or HolographicService
            self._holographic_service = factory(self.db)
        return self._holographic_service

    def _load_source(self, source_type: str, source_id: str) -> tuple:
        """根据来源类型与 ID 加载源数据、标题与内容。

        参数:
            source_type: 来源类型（insight / case / compliance）
            source_id: 来源 ID

        返回:
            (source_data, source_title, source_content) 元组
        """
        source_data = None
        source_title = ""
        source_content = ""
        if source_type == "insight":
            repo = CrossCaseInsightsRepository(self._connection())
            row = repo.get_by_id(int(source_id))
            if row:
                source_title = row.get("title", "")
                source_content = f"Type: {row.get('insight_type', '')}. Summary: {row.get('summary', '')}. Detail: {row.get('detail', '')}"
                source_data = row
        elif source_type == "case":
            repo = DecisionCasesRepository(self._connection())
            row = repo.get_by_id(int(source_id))
            if row:
                source_title = row.get("name", "")
                source_content = f"Description: {row.get('description', '')}. Outcome: {row.get('outcome', '')}. Score: {row.get('outcome_score', 0)}"
                source_data = row
        elif source_type == "compliance":
            repo = ComplianceAuditRecordsRepository(self._connection())
            row = repo.get_by_id(int(source_id))
            if row:
                source_title = row.get("content", "")[:100]
                source_content = f"Content: {row.get('content', '')}. Risk: {row.get('risk_level', '')}. Score: {row.get('score', 0)}. Passed: {row.get('passed', 0)}"
                source_data = row
        return source_data, source_title, source_content

    def auto_store(self, source_type: str, source_id: str, uid: int, auth_header: str = "") -> dict:
        """通过 AI 评估记忆重要性并自动存储到记忆库。

        参数:
            source_type: 来源类型
            source_id: 来源 ID
            uid: 用户 ID
            auth_header: 可选，认证头

        返回:
            包含 stored、importance 等字段的字典
        """
        gate_repo = MemoryGatesRepository(self._connection())
        entry_repo = MemoryEntriesRepository(self._connection())
        gate = gate_repo.find_active_by_source_type(source_type)
        if not gate:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No active gate for source_type '{source_type}'")
        source_data, source_title, source_content = self._load_source(source_type, source_id)
        if not source_data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Source {source_type}/{source_id} not found")
        messages = [
            {"role": "system", "content": "判断这条信息的重要性，给出0到1之间的一个分数（只输出数字，不要任何其他文字）。"},
            {"role": "user", "content": source_content},
        ]
        try:
            ai_resp = self.ai_gateway.chat(messages=messages, temperature=0.3, max_tokens=256, user_id=uid)
        except Exception:  # noqa: BLE001  # AI gateway call can fail for many reasons
            logger.exception("AI importance scoring call failed")
            return {"stored": False, "importance": 0, "error": "AI call failed"}
        raw = ai_resp.get("reply", "0")
        try:
            importance = float(raw.strip())
            importance = max(0.0, min(1.0, importance))
        except (ValueError, TypeError):
            importance = 0.0
        stored = importance >= gate["importance_threshold"]
        if stored:
            existing = entry_repo.find_by_source_active(source_type, source_id)
            if existing:
                return {"stored": False, "importance": importance, "reason": "Already stored"}
            now = _now()
            tags = json.dumps([source_type], ensure_ascii=False)
            entry_id = entry_repo.create(
                {
                    "title": source_title,
                    "content": source_content,
                    "memory_type": source_type,
                    "source_type": source_type,
                    "source_id": source_id,
                    "importance": importance,
                    "context_tags": tags,
                    "access_count": 0,
                    "created_by": uid,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            self.holographic_service.auto_associate(
                entry_id, {"context_tags": tags, "source_id": source_id, "memory_type": source_type, "created_at": now}
            )
        return {"stored": stored, "importance": importance}
