"""SOAP 决策解析与记录方法。"""

import json
from typing import Optional

from fastapi import HTTPException
from starlette import status as http_status

from cloud.app.repositories import SoapDecisionsRepository, SoapTemplatesRepository
from cloud.app.services.rep_workbench.soap_decision_validator import SoapDecisionValidatorMixin, _row
from shared.base import PaginatedResponse, validate_columns
from shared.columns import TABLE_SOAP_DECISIONS_COLS


class SoapDecisionParserMixin(SoapDecisionValidatorMixin):
    """SOAP 决策记录和异步意见的 JSON 解析方法。"""

    def create_decision(
        self,
        title: str,
        template_id: Optional[int],
        subjective: str,
        objective: str,
        assessment: str,
        plan: str,
        priority: str,
        tags: list,
        created_by,
    ) -> dict:
        """创建 SOAP 决策记录（S-O-A-P 四要素）。

        Args:
            title: 决策标题
            template_id: 关联模板 ID
            subjective: 主观信息（S）
            objective: 客观信息（O）
            assessment: 评估（A）
            plan: 计划（P）
            priority: 优先级
            tags: 标签列表
            created_by: 创建者 ID

        Returns:
            创建的决策记录
        """
        templates_repo = SoapTemplatesRepository(self._connection())
        decisions_repo = SoapDecisionsRepository(self._connection())
        if template_id:
            tmpl = templates_repo.get_by_id(template_id)
            if not tmpl or not tmpl.get("is_active"):
                raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail="Template not found")
        dec_id = decisions_repo.create(
            {
                "title": title,
                "template_id": template_id,
                "subjective": subjective,
                "objective": objective,
                "assessment": assessment,
                "plan": plan,
                "priority": priority,
                "tags": json.dumps(tags, ensure_ascii=False),
                "created_by": created_by,
                "updated_at": "NOW()",
            }
        )
        decisions_repo.execute("UPDATE soap_decisions SET updated_at=NOW() WHERE id=?", (dec_id,))
        self.db.commit()
        row = decisions_repo.get_by_id(dec_id)
        return _row(row, ["tags"])

    def list_decisions(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tag: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页查询决策列表。

        Args:
            status: 按状态筛选
            priority: 按优先级筛选
            tag: 按标签筛选
            page: 页码
            page_size: 每页条数

        Returns:
            分页决策列表
        """
        decisions_repo = SoapDecisionsRepository(self._connection())
        total, tp, items = decisions_repo.list_active_filtered(status=status, priority=priority, tag=tag, page=page, page_size=page_size)
        return PaginatedResponse(
            items=[_row(r, ["tags"]) for r in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=tp,
        )

    def get_decision(self, decision_id: int) -> dict:
        """获取决策详情。

        Args:
            decision_id: 决策 ID

        Returns:
            决策记录
        """
        decisions_repo = SoapDecisionsRepository(self._connection())
        row = decisions_repo.get_by_id(decision_id)
        if not row or not row.get("is_active"):
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail="Decision not found")
        return _row(row, ["tags"])

    def update_decision(
        self,
        decision_id: int,
        subjective: Optional[str] = None,
        objective: Optional[str] = None,
        assessment: Optional[str] = None,
        plan: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> dict:
        """更新决策字段。

        Args:
            decision_id: 决策 ID
            subjective: 新主观信息
            objective: 新客观信息
            assessment: 新评估
            plan: 新计划
            priority: 新优先级
            tags: 新标签

        Returns:
            更新后的决策记录
        """
        decisions_repo = SoapDecisionsRepository(self._connection())
        row = decisions_repo.get_by_id(decision_id)
        if not row or not row.get("is_active"):
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail="Decision not found")
        updates = {}
        for f in ("subjective", "objective", "assessment", "plan", "priority"):
            v = locals().get(f)
            if v is not None:
                updates[f] = v
        if tags is not None:
            updates["tags"] = json.dumps(tags, ensure_ascii=False)
        if updates:
            updates["updated_at"] = "NOW()"
            validate_columns(updates, "soap_decisions", TABLE_SOAP_DECISIONS_COLS)
            updates_to_save = {k: v for k, v in updates.items() if v != "NOW()"}
            decisions_repo.update(decision_id, updates_to_save)
            decisions_repo.execute("UPDATE soap_decisions SET updated_at=NOW() WHERE id=?", (decision_id,))
            self.db.commit()
        row = decisions_repo.get_by_id(decision_id)
        return _row(row, ["tags"])
