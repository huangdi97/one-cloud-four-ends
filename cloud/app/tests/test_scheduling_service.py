from cloud.app.services.rep_workbench.scheduling_service import SchedulingService


class TestSchedulingService:
    def test_optimize_route_empty(self):
        svc = SchedulingService()
        result = svc.optimize_route(rep_id=1, date_range="2024-01-01")
        assert isinstance(result, list)
