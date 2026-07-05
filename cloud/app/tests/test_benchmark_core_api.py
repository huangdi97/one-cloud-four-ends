import sqlite3
import uuid

import pytest

from cloud.app import database as database_module
from cloud.app.repositories import CustomersRepository, PiRepository, ProductRepository
from cloud.app.services.compliance_svc.enforcer_service import EnforcerService
from cloud.app.services.platform_svc.auth_service import AuthService
from cloud.app.services.rep_workbench.hcp_sandbox_service import HcpSandboxService
from cloud.app.services.rep_workbench.opportunity_service import OpportunityService


def _get_db():
    conn = sqlite3.connect(database_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_benchmark_rows(db):
    auth = AuthService(db)
    username = f"bench_{uuid.uuid4().hex[:8]}"
    password = "testpass123"
    user = auth.register(username, password)
    user_id = user["user_id"]

    hcp_service = HcpSandboxService(db)
    for idx in range(10):
        hcp_service.create_profile(
            name=f"Bench HCP {idx}",
            title="主任医师",
            hospital="Bench Hospital",
            department="内科",
            specialty="肿瘤科",
            city="Shanghai",
            tier="A",
            traits={"index": idx},
            prescription_volume=100 + idx,
            influence_score=0.8,
            digital_engagement=0.6,
            user_id=user_id,
        )

    customers_repo = CustomersRepository(db)
    customer_id = customers_repo.create(
        {
            "name": "Bench Customer",
            "status": "active",
            "created_by": user_id,
        }
    )

    opp_service = OpportunityService(db)
    for idx in range(10):
        opp_service.create_opportunity(
            customer_id=customer_id,
            name=f"Bench Opportunity {idx}",
            description="Benchmark opportunity",
            stage="lead",
            estimated_value=10000 + idx,
            actual_value=0,
            assigned_to=user_id,
            close_date=None,
            notes="",
            user_id=user_id,
        )

    return auth, username, password, user_id


class TestCoreAPIPerformance:
    def test_pi_search(self, benchmark):
        db = _get_db()
        try:
            repo = PiRepository(db)
            result = benchmark(repo.search, "test")
            assert isinstance(result, list)
        finally:
            db.close()

    def test_product_search(self, benchmark):
        db = _get_db()
        try:
            repo = ProductRepository(db)
            result = benchmark(repo.search, "FBS")
            assert isinstance(result, list)
        finally:
            db.close()

    def test_compliance_enforce(self, benchmark):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        enforcer = EnforcerService(db)
        visit = {"notes": "正常拜访", "expenses": 0}
        result = benchmark(enforcer.check_visit, visit)
        assert isinstance(result, dict)

    def test_compliance_enforce_benchmark(self, benchmark):
        db = _get_db()
        try:
            service = EnforcerService(db)
            visit = {
                "rep_id": 1,
                "notes": "医生透露了本月处方量数据",
                "expenses": 0,
                "rep_verified": True,
                "location_type": "hospital",
                "call_type": "常规拜访",
            }
            result = benchmark(service.check_visit, visit)
            assert isinstance(result, dict)
            assert "violations" in result
        finally:
            db.close()

    def test_auth_login_benchmark(self, benchmark):
        db = _get_db()
        try:
            auth, username, password, _user_id = _seed_benchmark_rows(db)
            result = benchmark(auth.login, username, password, "visit")
            assert "access_token" in result
        finally:
            db.close()

    def test_hcp_list_benchmark(self, benchmark):
        db = _get_db()
        try:
            _auth, _username, _password, user_id = _seed_benchmark_rows(db)
            service = HcpSandboxService(db)
            result = benchmark(service.list_profiles, page=1, page_size=10)
            assert result.total >= 10
            assert result.page == 1
            assert result.page_size == 10
        finally:
            db.close()

    def test_opportunity_list_benchmark(self, benchmark):
        db = _get_db()
        try:
            _auth, _username, _password, user_id = _seed_benchmark_rows(db)
            service = OpportunityService(db)
            result = benchmark(service.list_opportunities, page=1, page_size=10)
            assert result["total"] >= 10
            assert result["page"] == 1
            assert result["page_size"] == 10
        finally:
            db.close()

    def test_langgraph_execution(self, benchmark):
        try:
            from cloud.lg_utils.graph import get_test_graph
        except ImportError:
            pytest.skip("langgraph not installed")

        graph = get_test_graph()
        result = benchmark(
            graph.invoke,
            {
                "messages": ["hello"],
                "next_agent": "",
                "metadata": {},
                "needs_review": False,
            },
            {"configurable": {"thread_id": "bench-test"}},
        )
        assert "processed_by_B" in result["messages"]

    def test_product_matching(self, benchmark):
        from cloud.app.services.rep_workbench.product_matching_service import _tokenize

        result = benchmark(_tokenize, "PCR amplification for DNA sequencing")
        assert isinstance(result, set)

    def test_dashboard_overview(self, benchmark):
        from cloud.app.services.rep_workbench.dashboard_service import DashboardService

        db = _get_db()
        try:
            service = DashboardService(db)
            result = benchmark(service.get_overview)
            assert isinstance(result, dict)
        finally:
            db.close()

    def test_auth_login(self, benchmark):
        from shared.auth import hash_password, verify_password

        hashed = hash_password("test_password_123")
        result = benchmark(verify_password, "test_password_123", hashed)
        assert result is True

    def test_compliance_engine(self, benchmark):
        from shared.compliance import check_content

        rules = [
            {"category": "prohibited_word", "keyword": "cure"},
            {"category": "prohibited_word", "keyword": "guarantee"},
            {"category": "mandatory_claim", "keyword": "consult your doctor"},
            {"category": "dosage_limit", "keyword": "dosage", "max_value": "100"},
            {"category": "comparative_claim", "keyword": ""},
        ]
        content = "This product helps with symptom relief. Please consult your doctor before use. Take 50mg daily."
        result = benchmark(check_content, content, rules)
        assert result.passed is True
        assert result.score == 1.0

    def test_research_pi_query(self, benchmark):
        from cloud.app.services.intel.research_pi_service import ResearchPiService

        service = ResearchPiService()
        result = benchmark(service.search, "test")
        assert isinstance(result, list)
