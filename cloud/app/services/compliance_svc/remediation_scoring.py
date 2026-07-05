"""复查评分服务 — 合规官对整改工单打分，通过归档/不通过退回。"""

import logging
from datetime import datetime, timezone

from cloud.app.services.compliance_svc.remediation_service import RemediationService

logger = logging.getLogger(__name__)


class ScoreResult:
    def __init__(
        self,
        order_id: str,
        score: int,
        notes: str,
        evidence_checked: bool,
        passed: bool,
        scored_at: str,
    ):
        self.order_id = order_id
        self.score = score
        self.notes = notes
        self.evidence_checked = evidence_checked
        self.passed = passed
        self.scored_at = scored_at

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "score": self.score,
            "notes": self.notes,
            "evidence_checked": self.evidence_checked,
            "passed": self.passed,
            "scored_at": self.scored_at,
        }


class ScoreService:
    """评分服务，处理整改工单的复查评分。"""

    def __init__(self, remediation_service: RemediationService):
        self._remediation = remediation_service

    def score_order(
        self,
        order_id: str,
        score: int,
        notes: str = "",
        evidence_checked: bool = False,
        operator: str = "system",
    ) -> dict:
        """对整改工单评分。

        分数规则：
        - 1-4: 不通过，退回整改阶段
        - 5: 通过，归档关闭

        Args:
            order_id: 工单ID
            score: 分数 1-5
            notes: 评分备注
            evidence_checked: 是否已查验证据
            operator: 操作人
        """
        if score < 1 or score > 5:
            return {"error": "score must be between 1 and 5"}

        now = datetime.now(timezone.utc).isoformat()
        passed = score >= 5

        if passed:
            result = self._remediation.transition(order_id, "scored", operator)
            if "error" not in result:
                result = self._remediation.transition(order_id, "closed", operator)
                if "error" not in result:
                    result = self._remediation.transition(order_id, "archived", operator)
        else:
            result = self._remediation.transition(order_id, "remediating", operator)

        if "error" in result:
            return result

        # 更新分数字段
        conn = self._remediation._get_db()
        conn.execute(
            "UPDATE remediation_orders SET score=?, notes=? WHERE order_id=?",
            (score, notes, order_id),
        )
        conn.commit()
        conn.close()

        score_result = ScoreResult(order_id, score, notes, evidence_checked, passed, now)
        return score_result.to_dict()
