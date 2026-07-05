from types import SimpleNamespace

from cloud.app.services.rep_workbench.visit_service import VisitService


class TestVisitService:
    def test_record_visit(self):
        svc = VisitService()
        body = SimpleNamespace(
            hcp_id=1, hcp_name="test", content="test visit", visit_type="field", evidence_photos=[], location="test", location_mode="auto"
        )
        result = svc.create_visit(body)
        assert result is not None
