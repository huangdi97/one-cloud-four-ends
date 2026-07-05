class TestAuditLogPagination:
    def test_audit_pagination(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        for i in range(3):
            resp = client.post(
                "/audit/logs",
                json={
                    "user_id": 1,
                    "action": f"page_test_{i}",
                    "entity_type": "test",
                    "entity_id": i,
                    "detail": f"Pagination test entry {i}",
                },
                headers=headers,
            )
            assert resp.status_code == 201

        resp = client.get(
            "/audit/logs?page=1&page_size=2",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 3
        assert len(data["items"]) <= 2


class TestComplianceDashboardRouter:
    def test_dashboard_summary(self, client, auth_token):
        resp = client.get(
            "/api/compliance/dashboard/summary",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "total_violations_today" in data

    def test_rep_violations(self, client, auth_token):
        resp = client.get(
            "/api/compliance/dashboard/reps/1",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rep_id" in data
        assert "violations" in data

    def test_dashboard_auth_required(self, client):
        resp = client.get("/api/compliance/dashboard/summary")
        assert resp.status_code == 401

        resp = client.get("/api/compliance/dashboard/reps/1")
        assert resp.status_code == 401


class TestEnforcerRouter:
    def test_enforce_visit(self, client, auth_token):
        resp = client.post(
            "/api/compliance/enforce",
            json={
                "visit_data": {
                    "rep_id": 1,
                    "notes": "Regular checkup visit with no issues.",
                    "expenses": 100,
                }
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "violations" in data
        assert "passed" in data

    def test_list_rules(self, client, auth_token):
        resp = client.get(
            "/api/compliance/enforce/rules",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rules" in data

    def test_enforce_auth_required(self, client):
        resp = client.post("/api/compliance/enforce", json={"visit_data": {}})
        assert resp.status_code == 401

        resp = client.get("/api/compliance/enforce/rules")
        assert resp.status_code == 401


class TestAuditLogFiltering:
    def test_audit_log_filter_by_action(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}
        client.post(
            "/audit/logs",
            json={"user_id": 1, "action": "filter_test", "entity_type": "test", "detail": "x"},
            headers=headers,
        )
        resp = client.get(
            "/audit/logs?action=filter_test",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1

    def test_audit_log_filter_by_date_range(self, client, auth_token):
        resp = client.get(
            "/audit/logs?start_date=2000-01-01&end_date=2099-12-31",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

    def test_audit_log_filter_no_match(self, client, auth_token):
        resp = client.get(
            "/audit/logs?action=nonexistent_action_xyz",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


class TestComplianceContentEdgeCases:
    def test_content_high_risk_pharma(self, client, auth_token):
        resp = client.post(
            "/contents/",
            json={
                "title": "High Risk",
                "body": "Buy now! This drug cures everything immediately 100% guarantee.",
                "category": "pharma",
                "tags": [],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["compliance_score"] < 1.0

    def test_content_medical_disclaimer(self, client, auth_token):
        resp = client.post(
            "/contents/",
            json={
                "title": "Disclaimer",
                "body": "This content is for informational purposes only. Consult your physician.",
                "category": "pharma",
                "tags": [],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["compliance_score"] >= 0.5

    def test_content_empty_body(self, client, auth_token):
        resp = client.post(
            "/contents/",
            json={"title": "Empty Body", "body": "", "category": "pharma", "tags": []},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (200, 422, 400)
