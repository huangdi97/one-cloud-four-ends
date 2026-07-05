from cloud.app.services.rep_workbench.user_service import UserService


class TestUserService:
    def test_list_users_empty(self):
        svc = UserService()
        result = svc.list_users()
        assert isinstance(result, list)
