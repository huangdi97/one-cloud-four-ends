"""MDT引擎服务，整合辩论与共识解析能力。"""

from cloud.app.services.collab.mdt_debater import MdtDebater
from cloud.app.services.collab.mdt_resolver import MdtResolver
from shared.base_service import BaseService


class MdtEngineService(BaseService):
    """MdtEngine 服务类。"""

    def __init__(self, db=None):
        super().__init__(db)
        self._debater = MdtDebater(db)
        self._resolver = MdtResolver(db)

    def create_session(self, body, uid: int) -> dict:
        """创建会话。

        Args:
            uid: 描述

        Returns:
            描述
        """
        return self._debater.create_session(body, uid)

    def list_sessions(self, status_filter, page: int, page_size: int) -> dict:
        """获取会话列表。

        Args:
            status_filter: 描述
            page: 描述
            page_size: 描述

        Returns:
            描述
        """
        return self._debater.list_sessions(status_filter, page, page_size)

    def get_session(self, session_id: int) -> dict:
        """获取会话。

        Args:
            session_id: 描述

        Returns:
            描述
        """
        return self._debater.get_session(session_id)

    def debate(self, session_id: int, max_rounds: int, auth_header: str) -> dict:
        """debate 操作。

        Args:
            session_id: 描述
            max_rounds: 描述
            auth_header: 描述

        Returns:
            描述
        """
        return self._debater.debate(session_id, max_rounds, auth_header)

    def consensus(self, session_id: int, auth_header: str) -> dict:
        """consensus 操作。

        Args:
            session_id: 描述
            auth_header: 描述

        Returns:
            描述
        """
        return self._resolver.consensus(session_id, auth_header)

    def get_opinions(self, session_id: int, round_number: int | None = None) -> dict:
        """get_opinions 操作。

        Args:
            session_id: 描述
            round_number: 描述

        Returns:
            描述
        """
        return self._debater.get_opinions(session_id, round_number)

    def timeline(self, session_id: int) -> dict:
        """timeline 操作。

        Args:
            session_id: 描述

        Returns:
            描述
        """
        return self._debater.timeline(session_id)

    def dashboard(self) -> dict:
        """dashboard 操作。

        Returns:
            描述
        """
        return self._resolver.dashboard()
