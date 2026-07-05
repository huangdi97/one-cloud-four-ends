from cloud.app.services.bidding.admission_service import AdmissionService


class TestAdmissionService:
    def test_create_admission(self):
        svc = AdmissionService()
        result = svc.create({"hospital_name": "test", "product": "test_product"})
        assert isinstance(result, dict)
