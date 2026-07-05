"""Flying inspection task CRUD operations."""

from uuid import uuid4

from fastapi import HTTPException
from starlette import status

from cloud.app.schemas.flying_inspection import InspectionChecklist, InspectionTask, TaskStatus
from cloud.app.services.compliance_svc.capa_workflow_service import _add_audit_log, _append_history
from cloud.app.services.platform_svc.flying_inspection_calculation import compute_dashboard

from ._flying_inspection_data import AUDIT_TRAILS, CHECKLIST, DEFAULT_INSPECTION_ID, HISTORY, TASKS


def get_dashboard():
    """委托计算引擎返回飞检准备度仪表盘。"""
    return compute_dashboard(CHECKLIST, HISTORY)


def get_checklist(category: str | None = None) -> list[InspectionChecklist]:
    """获取检查清单，可按分类筛选。"""
    if not category:
        return CHECKLIST
    return [item for item in CHECKLIST if item.category == category]


def create_remediation_task(
    title: str,
    description: str,
    assignee: str,
    deadline: str,
    inspection_id: str = DEFAULT_INSPECTION_ID,
    who: str = "质量负责人",
    evidence: str = "remediation-task-form",
) -> InspectionTask:
    """创建整改任务并记录审计日志与历史。"""
    task_id = f"task-{uuid4().hex[:8]}"
    task = InspectionTask(id=task_id, title=title, description=description, assignee=assignee, deadline=deadline, status=TaskStatus.PENDING)
    TASKS[task_id] = task
    _add_audit_log(inspection_id=inspection_id, stage="remediation_assignment", who=who, what=f"分派整改任务给{assignee}：{title}", evidence=evidence)
    _append_history(
        inspection_id=inspection_id, event=f"创建整改任务：{title}", score=get_dashboard().score, owner=assignee, capa_stage="remediation_assignment"
    )
    return task


def get_history() -> list[dict]:
    """获取历史记录列表，每条记录附带完整的审计链。"""
    enriched = []
    for record in HISTORY:
        inspection_id = record.get("inspection_id", DEFAULT_INSPECTION_ID)
        enriched.append({**record, "audit_chain": AUDIT_TRAILS.get(inspection_id, []), "audit_count": len(AUDIT_TRAILS.get(inspection_id, []))})
    return enriched


def get_audit_trail(inspection_id: str) -> dict:
    """获取指定飞检周期的完整审计追踪链。"""
    trail = AUDIT_TRAILS.get(inspection_id)
    if trail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Inspection audit trail not found")
    return {
        "inspection_id": inspection_id,
        "capa_chain": ["compliance_self_check", "remediation_assignment", "review_confirmation", "scoring"],
        "audit_trail": trail,
    }
