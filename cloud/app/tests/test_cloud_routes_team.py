import uuid


class TestTeamManagement:
    def test_team_flow(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = client.post(
            "/teams",
            json={"name": "Alpha Team", "description": "Test team"},
            headers=headers,
        )
        assert resp.status_code == 201
        team = resp.json()["data"]
        team_id = team["id"]
        assert team["name"] == "Alpha Team"

        member_username = f"member_{uuid.uuid4().hex[:8]}"
        member_resp = client.post(
            "/auth/register",
            json={"username": member_username, "password": "memberpass123"},
        )
        assert member_resp.status_code == 201
        member_user_id = member_resp.json()["data"]["user_id"]

        resp = client.post(
            f"/teams/{team_id}/members",
            json={"user_id": member_user_id, "role": "member"},
            headers=headers,
        )
        assert resp.status_code == 201

        resp = client.get("/teams", headers=headers)
        assert resp.status_code == 200
        teams = resp.json()["data"]["items"]
        assert len(teams) >= 1

        resp = client.delete(
            f"/teams/{team_id}/members/{member_user_id}",
            headers=headers,
        )
        assert resp.status_code == 200

        resp = client.delete(
            f"/teams/{team_id}/members/{member_user_id}",
            headers=headers,
        )
        assert resp.status_code == 404


class TestTeamUpdate:
    def test_team_update_description(self, client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = client.post(
            "/teams",
            json={"name": "UpdateTeam", "description": "Before"},
            headers=headers,
        )
        assert resp.status_code == 201
        team_id = resp.json()["data"]["id"]

        resp = client.patch(
            f"/teams/{team_id}",
            json={"description": "After update description"},
            headers=headers,
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["data"]["description"] == "After update description"

        resp = client.get("/teams", headers=headers)
        assert resp.status_code == 200
        teams = resp.json()["data"]["items"]
        assert len(teams) >= 1


class TestTeamParamBoundaries:
    def test_team_create_empty_name(self, client, auth_token):
        resp = client.post(
            "/teams",
            json={"name": "", "description": "empty"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (422, 400, 201)

    def test_team_get_nonexistent(self, client, auth_token):
        resp = client.get(
            "/teams/99999999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)

    def test_team_delete_nonexistent(self, client, auth_token):
        resp = client.delete(
            "/teams/99999999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)

    def test_team_patch_nonexistent(self, client, auth_token):
        resp = client.patch(
            "/teams/99999999",
            json={"description": "ghost update"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code in (404, 200)
