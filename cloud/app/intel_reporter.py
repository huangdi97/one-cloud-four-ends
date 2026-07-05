"""情报报告器，管理洞察列表。"""

from typing import Optional

from cloud.app.services.compliance_svc.decision_intel_service import DecisionIntelService
from shared.base import PaginatedResponse, success


class IntelReporter:
    def list_insights(
        self,
        insight_type: Optional[str],
        confidence_min: Optional[float],
        page: int,
        page_size: int,
        current_user,
        service: DecisionIntelService,
    ):
        result = service.list_insights(
            insight_type=insight_type,
            confidence_min=confidence_min,
            page=page,
            page_size=page_size,
        )
        return success(
            data=PaginatedResponse(
                items=result["items"],
                total=result["total"],
                page=result["page"],
                page_size=result["page_size"],
                total_pages=result["total_pages"],
            )
        )

    def get_insight(self, insight_id: int, current_user, service: DecisionIntelService):
        row = service.get_insight(insight_id)
        return success(data=row)

    def update_insight(self, insight_id: int, body, current_user, service: DecisionIntelService):
        row = service.update_insight(
            insight_id=insight_id,
            title=body.title,
            summary=body.summary,
            confidence=body.confidence,
            applicability=body.applicability,
        )
        return success(data=row)

    def dashboard(self, current_user, service: DecisionIntelService):
        result = service.dashboard()
        return success(data=result)
