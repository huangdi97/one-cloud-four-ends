"""CAPA 事件驱动服务 — 异常事件自动触发整改任务创建与闭环管理。"""

from cloud.app.schemas.flying_inspection import InspectionTask, TaskStatus
from cloud.app.services.platform_svc._flying_inspection_data import CHECKLIST, DEFAULT_INSPECTION_ID, HISTORY
from cloud.app.services.platform_svc.flying_inspection_calculation import compute_dashboard
from cloud.app.services.platform_svc.flying_inspection_crud import create_remediation_task


class AnomalyEvent:
    """异常事件值对象。"""

    def __init__(self, event_id: str, event_type: str, description: str, responsible_agent: str, deadline: str):
        self.event_id = event_id
        self.event_type = event_type
        self.description = description
        self.responsible_agent = responsible_agent
        self.deadline = deadline


class CAPAEventService:
    """CAPA 事件服务 — 异常事件 → 整改任务自动创建 → 闭环确认。"""

    def create_remediation_from_anomaly(self, anomaly: AnomalyEvent, who: str = "合规引擎") -> InspectionTask:
        """异常事件触发后自动创建整改任务。"""
        task = create_remediation_task(
            title=f"[{anomaly.event_type}] {anomaly.description[:60]}",
            description=f"事件 ID：{anomaly.event_id}\n{anomaly.description}",
            assignee=anomaly.responsible_agent,
            deadline=anomaly.deadline,
            inspection_id=DEFAULT_INSPECTION_ID,
            who=who,
            evidence=f"anomaly-event-{anomaly.event_id}",
        )
        return task

    def get_open_tasks_for_agent(self, agent: str) -> list[InspectionTask]:
        """查询指定 Agent 的未完成任务。"""
        from cloud.app.services.platform_svc._flying_inspection_data import TASKS

        return [task for task in TASKS.values() if task.assignee == agent and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)]

    def complete_task_and_close_loop(self, task_id: str, who: str = "质量负责人", evidence: str = "remediation-evidence") -> InspectionTask:
        """确认整改完成，回写闭环状态。"""
        from cloud.app.services.compliance_svc.capa_workflow_service import confirm_remediation

        return confirm_remediation(
            task_id=task_id,
            inspection_id=DEFAULT_INSPECTION_ID,
            who=who,
            evidence=evidence,
        )

    def get_inspection_dashboard(self):
        """获取当前飞检仪表盘状态。"""
        return compute_dashboard(CHECKLIST, HISTORY)
