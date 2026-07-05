"""合规 V2 报告模块，提供审计复核、审计链查验、纠偏训练与仪表盘。"""

import hashlib
import json
import math
from typing import Optional

from cloud.app.repositories import (
    AuditChainEntriesRepository,
    ComplianceAuditRecordsRepository,
    TrainingCorrectionsRepository,
)
from cloud.app.services.rep_workbench.report_templates import (
    ReportTemplateMixin,
    _n404,
    _now,
    _parse_json,
)
from shared.base import PaginatedResponse, success
from shared.base_service import BaseService


class ReportFormatterMixin:
    """报告格式输出方法，提供纠偏训练相关功能。"""

    def list_corrections(
        self,
        category: Optional[str],
        severity: Optional[str],
        status: Optional[str],
        page: int,
        page_size: int,
    ) -> dict:
        """分页查询纠偏训练列表。

        Args:
            category: 按类别筛选
            severity: 按严重程度筛选
            status: 按状态筛选
            page: 页码
            page_size: 每页条数

        Returns:
            分页结果
        """
        repo = TrainingCorrectionsRepository(self._connection())
        conditions, params = [], []
        if category:
            conditions.append("category=?")
            params.append(category)
        if severity:
            conditions.append("severity=?")
            params.append(severity)
        if status:
            conditions.append("status=?")
            params.append(status)
        total, _, rows = repo.paginate(
            page=page,
            page_size=page_size,
            conditions=conditions or None,
            params=params or None,
            order_by="created_at DESC",
        )
        total_pages = math.ceil(total / max(page_size, 1))
        return success(
            data=PaginatedResponse(
                items=rows,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
        )

    def update_correction(self, correction_id: int, body) -> dict:
        """更新纠偏训练状态。

        Args:
            correction_id: 纠偏记录 ID
            body: 请求体（含 status、assigned_to）

        Returns:
            更新后的纠偏记录
        """
        repo = TrainingCorrectionsRepository(self._connection())
        row = repo.get_by_id(correction_id)
        if not row:
            _n404("Correction")
        updates = {}
        if body.status is not None:
            updates["status"] = body.status
        if body.assigned_to is not None:
            updates["assigned_to"] = body.assigned_to
        if updates:
            repo.update(correction_id, updates)
        return success(data=repo.get_by_id(correction_id))


class ReportGenerator(ReportTemplateMixin, ReportFormatterMixin, BaseService):
    """报告生成器，提供记录复核、哈希链审计、AI 纠偏训练及统计仪表盘。"""

    def review_record(self, record_id: int, body, uid: int) -> dict:
        """复核合规记录并写入审计链。

        Args:
            record_id: 审计记录 ID
            body: 请求体（含 review_notes、override_passed）
            uid: 复核者 ID

        Returns:
            复核后的记录
        """
        audit_repo = ComplianceAuditRecordsRepository(self._connection())
        chain_repo = AuditChainEntriesRepository(self._connection())
        row = audit_repo.get_by_id(record_id)
        if not row:
            _n404("Record")
        n = _now()
        audit_repo.update(record_id, {"reviewed_by": uid, "reviewed_at": n})
        chain_repo.create(
            {
                "entity_type": "compliance_audit",
                "entity_id": str(record_id),
                "action": "review",
                "previous_hash": "",
                "current_hash": hashlib.sha256(
                    json.dumps(
                        {
                            "action": "review",
                            "record_id": record_id,
                            "notes": body.review_notes,
                        }
                    ).encode()
                ).hexdigest(),
                "payload": json.dumps(
                    {
                        "override_passed": body.override_passed,
                        "review_notes": body.review_notes,
                    },
                    ensure_ascii=False,
                ),
                "source": "",
                "created_by": uid,
                "performed_at": n,
            }
        )
        return success(data=audit_repo.get_by_id(record_id))

    def create_audit_chain(self, body, uid: int) -> dict:
        """创建审计链条目（追加哈希链接）。

        Args:
            body: 请求体（含 entity_type、entity_id、action、payload）
            uid: 操作者 ID

        Returns:
            含 current_hash 和 previous_hash 的确认信息
        """
        repo = AuditChainEntriesRepository(self._connection())
        n = _now()
        prev_hash = ""
        latest_rows = repo.list_all(
            conditions=["entity_type=?", "entity_id=?"],
            params=[body.entity_type, body.entity_id],
            order_by="performed_at DESC",
        )
        if latest_rows:
            prev_hash = latest_rows[0]["current_hash"]
        current_hash = hashlib.sha256((prev_hash + json.dumps(body.payload, ensure_ascii=False, sort_keys=True)).encode("utf-8")).hexdigest()
        repo.create(
            {
                "entity_type": body.entity_type,
                "entity_id": body.entity_id,
                "action": body.action,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "payload": json.dumps(body.payload, ensure_ascii=False),
                "metadata": json.dumps(body.metadata, ensure_ascii=False),
                "source": body.source,
                "created_by": uid,
                "performed_at": n,
            }
        )
        return success(
            data={
                "entity_type": body.entity_type,
                "entity_id": body.entity_id,
                "current_hash": current_hash,
                "previous_hash": prev_hash,
            }
        )

    def get_audit_chain(self, entity_type: str, entity_id: str) -> dict:
        """获取指定实体的审计链。

        Args:
            entity_type: 实体类型
            entity_id: 实体 ID

        Returns:
            审计链条目列表
        """
        repo = AuditChainEntriesRepository(self._connection())
        rows = repo.list_all(
            conditions=["entity_type=?", "entity_id=?"],
            params=[entity_type, entity_id],
            order_by="performed_at ASC",
        )
        return success(data=rows)

    def verify_audit_chain(self, entity_type: str, entity_id: str) -> dict:
        """验证审计链完整性（哈希比对）。

        Args:
            entity_type: 实体类型
            entity_id: 实体 ID

        Returns:
            含 valid、total_entries 和 broken_at 的验证结果
        """
        repo = AuditChainEntriesRepository(self._connection())
        rows = repo.list_all(
            conditions=["entity_type=?", "entity_id=?"],
            params=[entity_type, entity_id],
            order_by="performed_at ASC",
        )
        valid = True
        broken_at = None
        for i, row in enumerate(rows):
            expected_prev = rows[i - 1]["current_hash"] if i > 0 else ""
            if row["previous_hash"] != expected_prev:
                valid = False
                broken_at = row["id"]
                break
            payload = _parse_json(row["payload"], {}) if isinstance(row["payload"], str) else row["payload"]
            recomputed = hashlib.sha256((row["previous_hash"] + json.dumps(payload, ensure_ascii=False, sort_keys=True)).encode("utf-8")).hexdigest()
            if recomputed != row["current_hash"]:
                valid = False
                broken_at = row["id"]
                break
        return success(
            data={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "valid": valid,
                "total_entries": len(rows),
                "broken_at": broken_at,
            }
        )
