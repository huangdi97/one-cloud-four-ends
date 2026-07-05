"""通知服务，负责通知模板管理与消息发送、列表查询及已读标记。"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from starlette import status

from cloud.app.config.provider_config import ProviderMode, ProviderSettings
from cloud.app.repositories import (
    NotificationsRepository,
    NotificationTemplatesRepository,
)
from cloud.app.services.agent_ops.api_providers import ApiPush
from cloud.app.services.platform_svc.local_providers import LocalPush
from cloud.app.services.rep_workbench.notification_builder import NotificationBuilderMixin, _render_template
from shared.base_service import BaseService

logger = logging.getLogger(__name__)


def _notification_to_dict(row) -> dict:
    """将数据库行转换为通知字典。

    Args:
        row: 数据库查询结果行

    Returns:
        通知信息字典
    """
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "template_id": row["template_id"],
        "title": row["title"],
        "body": row["body"],
        "category": row["category"],
        "ref_type": row["ref_type"],
        "ref_id": row["ref_id"],
        "context_json": row["context_json"],
        "is_read": row["is_read"],
        "read_at": row["read_at"],
        "created_at": row["created_at"],
    }


class NotificationService(NotificationBuilderMixin, BaseService):
    """通知服务，提供模板管理、消息发送、列表查询与已读标记功能。"""

    def __init__(self, db=None, provider_settings: ProviderSettings | None = None) -> None:
        super().__init__(db)
        self._push_settings = provider_settings or ProviderSettings(service="push")

    def _push_notification(self, title: str, body: str, user_id: int) -> None:
        if not self._push_settings.enabled:
            logger.info("Push disabled, skipping push for user_id=%d", user_id)
            return
        recipient = str(user_id)
        message = f"{title}: {body}"
        if self._push_settings.mode == ProviderMode.API:
            provider = ApiPush(self._push_settings)
        else:
            provider = LocalPush(self._push_settings)
        provider.send(recipient, message)

    def send(
        self,
        user_id: int,
        template_name: Optional[str] = None,
        title: Optional[str] = None,
        body: Optional[str] = None,
        category: Optional[str] = None,
        context: Optional[dict] = None,
        ref_type: Optional[str] = None,
        ref_id: Optional[int] = None,
    ) -> dict:
        """发送通知，支持直接指定内容或使用模板。

        Args:
            user_id: 目标用户ID
            template_name: 模板名称（可选）
            title: 通知标题（可选）
            body: 通知正文（可选）
            category: 通知分类（可选）
            context: 模板渲染上下文（可选）
            ref_type: 关联对象类型（可选）
            ref_id: 关联对象ID（可选）

        Returns:
            创建的通知字典

        Raises:
            HTTPException: 模板不存在或缺少必要参数时返回对应错误
        """
        title = title
        body_text = body
        category = category
        template_id = None
        context_json = ""
        db = self.db

        if template_name:
            tmpl_repo = NotificationTemplatesRepository(db)
            rows = tmpl_repo.list_all(conditions=["name=?"], params=[template_name])
            if not rows:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
            template = rows[0]
            ctx = context or {}
            title = _render_template(template["title_template"], ctx)
            body_text = _render_template(template["body_template"], ctx)
            category = category or template["category"]
            template_id = template["id"]
            context_json = json.dumps(ctx, ensure_ascii=False)

        if not title or not body_text or not category:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="title, body, and category are required (or provide template_name + context)",
            )

        notif_repo = NotificationsRepository(db)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_id = notif_repo.create(
            {
                "user_id": user_id,
                "template_id": template_id,
                "title": title,
                "body": body_text,
                "category": category,
                "ref_type": ref_type or "",
                "ref_id": ref_id,
                "context_json": context_json,
                "created_at": now,
            }
        )
        row = notif_repo.get_by_id(row_id)
        self._push_notification(title=title, body=body_text, user_id=user_id)
        return _notification_to_dict(row)

    def list_notifications(
        self,
        user_id: int,
        is_read: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询通知列表，支持按已读状态筛选和分页。

        Args:
            user_id: 用户ID
            is_read: 已读状态筛选（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            包含 items、total、page、page_size 的字典
        """
        conditions = ["user_id=?"]
        params = [user_id]
        if is_read is not None:
            conditions.append("is_read=?")
            params.append(is_read)

        notif_repo = NotificationsRepository(self._connection())
        total, _, items = notif_repo.paginate(
            page=page,
            page_size=page_size,
            conditions=conditions,
            params=params,
            order_by="created_at DESC",
        )
        return {
            "items": [_notification_to_dict(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def mark_read(self, notification_id: int, user_id: int) -> dict:
        """将通知标记为已读。

        Args:
            notification_id: 通知ID
            user_id: 用户ID

        Returns:
            更新后的通知字典

        Raises:
            HTTPException: 通知不存在时返回404
        """
        notif_repo = NotificationsRepository(self._connection())
        db = self.db
        placeholders = ", ".join(notif_repo.cols)
        row = db.execute(
            f"SELECT {placeholders} FROM {notif_repo.table_name} WHERE id=? AND user_id=?",
            (notification_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notif_repo.update(notification_id, {"is_read": 1, "read_at": now})
        row = notif_repo.get_by_id(notification_id)
        return _notification_to_dict(row)

    def unread_count(self, user_id: int) -> dict:
        """查询用户未读通知数量。

        Args:
            user_id: 用户ID

        Returns:
            包含未读计数的字典
        """
        notif_repo = NotificationsRepository(self._connection())
        count = notif_repo.count(conditions=["user_id=?", "is_read=0"], params=[user_id])
        return {"count": count}
