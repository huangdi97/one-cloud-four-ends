"""Tests: CAPA anomaly event → remediation task auto-creation → close loop."""

from cloud.app.schemas.flying_inspection import TaskStatus
from cloud.app.services.compliance_svc.capa_event_service import AnomalyEvent, CAPAEventService


class TestCAPAEventService:
    def test_anomaly_event_creates_remediation_task(self):
        svc = CAPAEventService()
        anomaly = AnomalyEvent(
            event_id="anomaly-001",
            event_type="冷链异常",
            description="冷链温度超标，需立即复核校准记录",
            responsible_agent="仓储主管",
            deadline="2026-06-20",
        )

        task = svc.create_remediation_from_anomaly(anomaly)

        assert task.id.startswith("task-")
        assert task.title == "[冷链异常] 冷链温度超标，需立即复核校准记录"
        assert task.assignee == "仓储主管"
        assert task.deadline == "2026-06-20"
        assert task.status == TaskStatus.PENDING

    def test_anomaly_event_with_checklist_failure(self):
        svc = CAPAEventService()
        anomaly = AnomalyEvent(
            event_id="anomaly-002",
            event_type="资质证照过期",
            description="营业执照即将到期，需更换新证",
            responsible_agent="质量负责人",
            deadline="2026-06-25",
        )

        task = svc.create_remediation_from_anomaly(anomaly)

        assert task.assignee == "质量负责人"
        assert task.status == TaskStatus.PENDING

    def test_get_open_tasks_for_agent(self):
        svc = CAPAEventService()
        tasks = svc.get_open_tasks_for_agent("仓储主管")
        assert len(tasks) >= 1
        for t in tasks:
            assert t.assignee == "仓储主管"

    def test_complete_task_and_close_loop(self):

        svc = CAPAEventService()
        anomaly = AnomalyEvent(
            event_id="anomaly-003",
            event_type="样品管理",
            description="样品台账不一致，需重新核对",
            responsible_agent="医学事务",
            deadline="2026-06-22",
        )

        task = svc.create_remediation_from_anomaly(anomaly)
        assert task.status == TaskStatus.PENDING

        completed = svc.complete_task_and_close_loop(task_id=task.id, who="医学事务", evidence="sample-ledger-review")
        assert completed.status == TaskStatus.CONFIRMED

    def test_dashboard_accessible(self):
        svc = CAPAEventService()
        dashboard = svc.get_inspection_dashboard()
        assert dashboard.score >= 0
        assert dashboard.score <= 100
