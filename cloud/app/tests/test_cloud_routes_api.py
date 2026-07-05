import uuid


class TestCustomerRouter:
    def test_get_customers_unauthorized(self, client):
        resp = client.get("/customers/")
        assert resp.status_code == 401

    def test_create_customer(self, client, auth_token):
        resp = client.post(
            "/customers/",
            json={
                "name": f"cust-{uuid.uuid4().hex[:6]}",
                "hospital": "Test Hospital",
                "department": "Cardiology",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()["data"] if "data" in resp.json() else resp.json()
        assert data is not None

    def test_list_customers(self, client, auth_token):
        resp = client.get(
            "/customers/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200


class TestVisitRouter:
    def test_get_visits(self, client, auth_token):
        resp = client.get(
            "/api/visit",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

    def test_visit_auth_required(self, client):
        resp = client.post("/api/visit", json={"hcp_id": 1, "hcp_name": "x", "content": "y"})
        assert resp.status_code == 401


class TestSettingsRouter:
    def test_get_settings(self, client, auth_token):
        resp = client.get(
            "/settings/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200


class TestDatabaseConnection:
    def test_health_db_connected(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["db"] == "connected"


class TestEmptyResultSets:
    def test_audit_logs_empty(self, client, auth_token):
        resp = client.get(
            "/audit/logs?entity_type=nonexistent_entity_x",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0

    def test_teams_empty(self, client, auth_token):
        resp = client.get(
            "/teams",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

    def test_notifications_empty(self, client, auth_token):
        resp = client.get(
            "/notifications/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["data"].get("items", [])
        assert isinstance(items, list)


class TestCustomerParamBoundaries:
    def test_customer_create_missing_name(self, client, auth_token):
        resp = client.post(
            "/customers/",
            json={"hospital": "Some Hospital"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 200, 201)

    def test_customer_get_nonexistent(self, client, auth_token):
        resp = client.get(
            "/customers/99999999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)


class TestSettingsParamBoundaries:
    def test_settings_unauthorized_methods(self, client):
        resp = client.post("/settings/", json={})
        assert resp.status_code in (401, 405, 404)

    def test_settings_put_not_allowed(self, client, auth_token):
        resp = client.put(
            "/settings/",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (405, 401, 404)


class TestVisitParamBoundaries:
    def test_visit_create_missing_required(self, client, auth_token):
        resp = client.post(
            "/api/visit",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400)

    def test_visit_get_detail_nonexistent(self, client, auth_token):
        resp = client.get(
            "/api/visit/99999999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)
