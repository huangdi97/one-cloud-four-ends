"""SOAP决策服务处理结构化评估与决策逻辑。"""

import json
from typing import Optional

from fastapi import HTTPException
from starlette import status as http_status

from cloud.app.repositories import (
    AsyncMdtOpinionsRepository,
    SoapDecisionsRepository,
    SoapTemplatesRepository,
)
from cloud.app.services.rep_workbench.soap_decision_parser import SoapDecisionParserMixin, _row
from shared.base_service import BaseService


class SoapDecisionService(SoapDecisionParserMixin, BaseService):
    """SOAP决策服务，提供模板管理、决策 CRUD、意见征询与最终裁定功能。"""

    def create_template(self, name: str, category: str, description: str, structure: dict, created_by) -> dict:
        """创建 SOAP 决策模板。

        Args:
            name: 模板名称
            category: 分类
            description: 描述
            structure: 结构化模板定义
            created_by: 创建者 ID

        Returns:
            创建的模板记录
        """
        templates_repo = SoapTemplatesRepository(self._connection())
        tmpl_id = templates_repo.create(
            {
                "name": name,
                "category": category,
                "description": description,
                "structure": json.dumps(structure, ensure_ascii=False),
                "created_by": created_by,
                "updated_at": "NOW()",
            }
        )
        templates_repo.execute("UPDATE soap_templates SET updated_at=NOW() WHERE id=?", (tmpl_id,))
        self.db.commit()
        row = templates_repo.get_by_id(tmpl_id)
        return _row(row, ["structure"])

    def list_templates(self, category: Optional[str] = None) -> list:
        """列出有效模板。

        Args:
            category: 按分类筛选

        Returns:
            模板列表
        """
        templates_repo = SoapTemplatesRepository(self._connection())
        rows = templates_repo.list_active(category=category)
        return [_row(r, ["structure"]) for r in rows]

    def submit_decision(self, decision_id: int) -> dict:
        """提交决策进入意见收集状态。

        Args:
            decision_id: 决策 ID

        Returns:
            更新后的决策记录
        """
        decisions_repo = SoapDecisionsRepository(self._connection())
        row = decisions_repo.get_by_id(decision_id)
        if not row or not row.get("is_active"):
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail="Decision not found")
        if row["status"] != "draft":
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                detail="Only draft decisions can be submitted",
            )
        decisions_repo.update(decision_id, {"status": "collecting"})
        decisions_repo.execute("UPDATE soap_decisions SET updated_at=NOW() WHERE id=?", (decision_id,))
        self.db.commit()
        row = decisions_repo.get_by_id(decision_id)
        return _row(row, ["tags"])

    def finalize_decision(self, decision_id: int, decision_summary: str, user_id) -> dict:
        """最终裁定决策，写入摘要和裁定者。

        Args:
            decision_id: 决策 ID
            decision_summary: 裁定摘要
            user_id: 裁定者 ID

        Returns:
            已裁定的决策记录
        """
        decisions_repo = SoapDecisionsRepository(self._connection())
        row = decisions_repo.get_by_id(decision_id)
        if not row or not row.get("is_active"):
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail="Decision not found")
        if row["status"] != "collecting":
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                detail="Only decisions in 'collecting' status can be finalized",
            )
        decisions_repo.update(
            decision_id,
            {
                "decision_summary": decision_summary,
                "status": "decided",
                "decided_by": user_id,
            },
        )
        decisions_repo.execute(
            "UPDATE soap_decisions SET decided_at=NOW(), updated_at=NOW() WHERE id=?",
            (decision_id,),
        )
        self.db.commit()
        row = decisions_repo.get_by_id(decision_id)
        return _row(row, ["tags"])

    def dashboard(self) -> dict:
        """SOAP 决策仪表盘，汇总决策与意见统计。

        Returns:
            含总数、状态分布、优先级分布和最近决策的字典
        """
        decisions_repo = SoapDecisionsRepository(self._connection())
        opinions_repo = AsyncMdtOpinionsRepository(self._connection())
        total = decisions_repo.count_active()
        by_status = decisions_repo.count_by_status()
        by_priority = decisions_repo.count_by_priority()
        total_opinions = opinions_repo.count_all()
        recent = decisions_repo.list_active_recent(5)
        return {
            "total_decisions": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "total_opinions": total_opinions,
            "recent_decisions": [_row(r, ["tags"]) for r in recent],
        }
