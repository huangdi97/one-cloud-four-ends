"""决策分析师，管理决策案例。"""

from typing import Optional

from cloud.app.services.compliance_svc.decision_intel_service import DecisionIntelService
from shared.base import PaginatedResponse, success


class DecisionAnalyst:
    def create_case(self, body, request, current_user, service: DecisionIntelService):
        uid = int(current_user["sub"])
        row = service.create_case(
            name=body.name,
            pipeline_run_id=body.pipeline_run_id,
            description=body.description,
            outcome=body.outcome,
            outcome_score=body.outcome_score,
            context=body.context,
            tags=body.tags,
            uid=uid,
        )
        return success(data=row)

    def list_cases(
        self,
        outcome_score_min: Optional[float],
        outcome_score_max: Optional[float],
        tag: Optional[str],
        search: Optional[str],
        page: int,
        page_size: int,
        current_user,
        service: DecisionIntelService,
    ):
        result = service.list_cases(
            outcome_score_min=outcome_score_min,
            outcome_score_max=outcome_score_max,
            tag=tag,
            search=search,
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

    def get_case(self, case_id: int, current_user, service: DecisionIntelService):
        row = service.get_case(case_id)
        return success(data=row)

    def update_case(self, case_id: int, body, current_user, service: DecisionIntelService):
        row = service.update_case(
            case_id=case_id,
            name=body.name,
            description=body.description,
            outcome=body.outcome,
            outcome_score=body.outcome_score,
            context=body.context,
            tags=body.tags,
        )
        return success(data=row)

    def delete_case(self, case_id: int, current_user, service: DecisionIntelService):
        service.delete_case(case_id)
        return success(message="deleted")

    def analyze_case(self, case_id: int, body, request, current_user, service: DecisionIntelService):
        auth_header = request.headers.get("Authorization", "")
        result = service.analyze_case(
            case_id=case_id,
            custom_question=body.custom_question,
            auth_header=auth_header,
        )
        return success(data=result)

    def list_analyses(self, case_id: int, current_user, service: DecisionIntelService):
        rows = service.list_analyses(case_id)
        return success(data=rows)

    def get_analysis(self, analysis_id: int, current_user, service: DecisionIntelService):
        row = service.get_analysis(analysis_id)
        return success(data=row)

    def reflect(self, body, request, current_user, service: DecisionIntelService):
        auth_header = request.headers.get("Authorization", "")
        result = service.reflect(
            filter_tags=body.filter_tags,
            max_cases=body.max_cases,
            auth_header=auth_header,
        )
        return success(data=result)
