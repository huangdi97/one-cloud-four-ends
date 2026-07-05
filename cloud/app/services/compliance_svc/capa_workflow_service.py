"""CAPA workflow — remediation and audit trail management."""

from uuid import uuid4

from fastapi import HTTPException
from starlette import status

from cloud.app.schemas.flying_inspection import InspectionTask, TaskStatus
from cloud.app.services.platform_svc._flying_inspection_data import AUDIT_TRAILS, CHECKLIST, DEFAULT_INSPECTION_ID, HISTORY, TASKS
from cloud.app.services.platform_svc.flying_inspection_calculation import compute_dashboard
from shared.datetime_utils import now as _now


def _add_audit_log(inspection_id: str, stage: str, who: str, what: str, evidence: str) -> dict:
    entry = {"id": f"audit-{uuid4().hex[:8]}", "stage": stage, "who": who, "when": _now(), "what": what, "evidence": evidence}
    AUDIT_TRAILS.setdefault(inspection_id, []).append(entry)
    return entry


def _append_history(inspection_id: str, event: str, score: int, owner: str, capa_stage: str) -> None:
    HISTORY.insert(
        0,
        {
            "id": f"hist-{uuid4().hex[:8]}",
            "inspection_id": inspection_id,
            "date": _now()[:10],
            "event": event,
            "score": score,
            "owner": owner,
            "capa_stage": capa_stage,
        },
    )


def confirm_remediation(
    task_id: str, inspection_id: str = DEFAULT_INSPECTION_ID, who: str = "质量负责人", evidence: str = "remediation-evidence"
) -> InspectionTask:
    """确认整改完成，更新任务状态并记录审计评分。"""
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Inspection task not found")
    confirmed = task.model_copy(update={"status": TaskStatus.CONFIRMED})
    TASKS[task_id] = confirmed
    _add_audit_log(inspection_id=inspection_id, stage="review_confirmation", who=who, what=f"复查确认整改完成：{confirmed.title}", evidence=evidence)
    score = compute_dashboard(CHECKLIST, HISTORY).score
    _add_audit_log(
        inspection_id=inspection_id, stage="scoring", who="合规评分引擎", what=f"飞检闭环评分更新为{score}", evidence="inspection-score-ledger"
    )
    _append_history(
        inspection_id=inspection_id, event=f"确认整改完成：{confirmed.title}", score=score, owner=confirmed.assignee, capa_stage="review_confirmation"
    )
    return confirmed
