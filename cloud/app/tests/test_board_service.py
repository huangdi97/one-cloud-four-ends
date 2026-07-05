from cloud.app.services.platform_svc.board_service import BoardService


class TestBoardService:
    def test_list_boards(self):
        svc = BoardService()
        result = svc.list_boards()
        assert isinstance(result, list)
