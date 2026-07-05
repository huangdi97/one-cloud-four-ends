from cloud.app.services.compliance_svc.audit_service import AuditService


class TestAuditService:
    def test_log_audit(self):
        svc = AuditService()
        svc.create_log(user_id=1, action="test_action", entity_type="test", detail="test_detail")
