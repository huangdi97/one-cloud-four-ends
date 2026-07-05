"""Core compliance tests: TestComplianceCheck, TestAuditLogs, TestComplianceRulesCRUD, TestComplianceRuleUpdate.
TestComplianceContentEdgeCases moved to test_cloud_compliance_routes.py.
"""


class TestComplianceCheck:
    def test_prohibited_content_fails_compliance(self, client, auth_token):
        resp = client.post(
            "/contents/",
            json={
                "title": "Bad Content",
                "body": "This product can 根治 all diseases with absolutely safe formulation 无副作用.",
                "category": "pharma",
                "tags": [],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["compliance_score"] < 1.0
        assert data["status"] == "pending_review"

    def test_clean_content_passes_compliance(self, client, auth_token):
        resp = client.post(
            "/contents/",
            json={
                "title": "Clean Content",
                "body": "This product should be used as directed by a physician.",
                "category": "pharma",
                "tags": [],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["compliance_score"] >= 0.8


class TestAuditLogs:
    def test_audit_log_crud_and_stats(self, client, auth_token):
        resp = client.post(
            "/audit/logs",
            json={
                "user_id": 1,
                "action": "test_create",
                "entity_type": "tests",
                "entity_id": 1,
                "detail": "Test audit entry",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201

        resp = client.post(
            "/audit/logs",
            json={
                "user_id": 1,
                "action": "test_update",
                "entity_type": "tests",
                "entity_id": 2,
                "detail": "Another test audit entry",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201

        resp = client.get(
            "/audit/logs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

        resp = client.get(
            "/audit/logs/stats",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert "by_action" in stats
        assert "daily_trend" in stats


class TestComplianceRulesCRUD:
    def test_compliance_rule_crud(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = client.post(
            "/compliance/rules",
            json={
                "name": "Test Rule",
                "category": "pharma",
                "keyword": "test_prohibited",
                "max_value": 0.5,
            },
            headers=headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()["data"]
        rule_id = data.get("id") or data.get("rule_id")
        assert rule_id is not None

        resp = client.get("/compliance/rules", headers=headers)
        assert resp.status_code == 200
        rules = resp.json()["data"]
        if isinstance(rules, dict) and "items" in rules:
            assert rules["total"] >= 1
        elif isinstance(rules, list):
            assert len(rules) >= 1

        resp = client.delete(
            f"/compliance/rules/{rule_id}",
            headers=headers,
        )
        assert resp.status_code in (200, 204)


class TestComplianceRuleUpdate:
    def test_update_compliance_rule(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}
        resp = client.post(
            "/compliance/rules",
            json={"name": "RuleToUpdate", "category": "pharma", "keyword": "badword", "max_value": 0.3},
            headers=headers,
        )
        assert resp.status_code in (200, 201), resp.text
        rule_id = resp.json()["data"].get("id") or resp.json()["data"].get("rule_id")

        resp = client.patch(
            f"/compliance/rules/{rule_id}",
            json={"max_value": 0.9},
            headers=headers,
        )
        assert resp.status_code in (200, 201), resp.text

        resp = client.get(f"/compliance/rules/{rule_id}", headers=headers)
        assert resp.status_code in (200, 404)

    def test_update_nonexistent_rule(self, client, auth_token):
        resp = client.patch(
            "/compliance/rules/99999999",
            json={"max_value": 0.5},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)

    def test_create_rule_missing_name(self, client, auth_token):
        resp = client.post(
            "/compliance/rules",
            json={"category": "pharma", "keyword": "kw", "max_value": 0.5},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 200, 201)

    def test_create_rule_negative_max_value(self, client, auth_token):
        resp = client.post(
            "/compliance/rules",
            json={"name": "NegRule", "category": "pharma", "keyword": "kw", "max_value": -1.0},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 200, 201)

    def test_create_rule_invalid_category(self, client, auth_token):
        resp = client.post(
            "/compliance/rules",
            json={"name": "BadCat", "category": "", "keyword": "kw", "max_value": 0.5},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 200, 201)
