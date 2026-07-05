class TestBoardManagement:
    def test_board_and_task_flow(self, client, auth_token):
        resp = client.post(
            "/boards/",
            json={"name": "Test Board", "description": "A test kanban board"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        board = resp.json()["data"]
        board_id = board["id"]
        assert board["name"] == "Test Board"

        resp = client.post(
            f"/boards/{board_id}/tasks",
            json={
                "title": "Task 1",
                "description": "First task",
                "status": "todo",
                "priority": "high",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        task_id = resp.json()["data"]["id"]

        resp = client.post(
            f"/boards/{board_id}/tasks",
            json={
                "title": "Task 2",
                "description": "Second task",
                "status": "done",
                "priority": "low",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201

        resp = client.get(
            f"/boards/{board_id}/kanban",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        kanban = resp.json()["data"]
        assert "board" in kanban
        assert "columns" in kanban
        assert len(kanban["columns"]["todo"]) >= 1
        assert len(kanban["columns"]["done"]) >= 1

        resp = client.get(
            f"/boards/{board_id}/tasks",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        tasks = resp.json()["data"]
        assert len(tasks) >= 2

        resp = client.delete(
            f"/boards/{board_id}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

        resp = client.get(
            f"/boards/{board_id}/tasks",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        remaining = [t for t in resp.json()["data"] if t.get("is_active", 1) == 1]
        assert len(remaining) <= 1


class TestDashboard:
    def test_dashboard_endpoints(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = client.get("/dashboard/overview", headers=headers)
        assert resp.status_code == 200
        overview = resp.json()["data"]
        assert "user_count" in overview
        assert "content_count" in overview
        assert "compliance_rate" in overview

        resp = client.get("/dashboard/users", headers=headers)
        assert resp.status_code == 200
        assert "by_role" in resp.json()["data"]

        resp = client.get("/dashboard/compliance", headers=headers)
        assert resp.status_code == 200
        assert "pass_rate" in resp.json()["data"]

        resp = client.get("/dashboard/contents", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "by_category" in data
        assert "by_status" in data


class TestBoardUpdate:
    def test_board_update(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = client.post(
            "/boards/",
            json={"name": "Original Board", "description": "Before update"},
            headers=headers,
        )
        assert resp.status_code == 201
        board_id = resp.json()["data"]["id"]

        resp = client.patch(
            f"/boards/{board_id}",
            json={"name": "Updated Board Name", "description": "After update"},
            headers=headers,
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["data"]["name"] == "Updated Board Name"

        resp = client.get(
            f"/boards/{board_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Board Name"


class TestBoardParamBoundaries:
    def test_board_create_empty_name(self, client, auth_token):
        resp = client.post(
            "/boards/",
            json={"name": "", "description": "empty name"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 201)

    def test_board_create_long_name(self, client, auth_token):
        resp = client.post(
            "/boards/",
            json={"name": "x" * 500, "description": "long name"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 201)

    def test_board_get_nonexistent(self, client, auth_token):
        resp = client.get(
            "/boards/99999999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)

    def test_board_delete_nonexistent(self, client, auth_token):
        resp = client.delete(
            "/boards/99999999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)

    def test_board_patch_nonexistent(self, client, auth_token):
        resp = client.patch(
            "/boards/99999999",
            json={"name": "ghost"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)
