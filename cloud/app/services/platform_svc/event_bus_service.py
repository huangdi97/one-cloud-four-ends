"""事件总线服务，负责事件定义、订阅与消息管理。"""

import json
import uuid
from typing import Optional

from fastapi import Depends, HTTPException
from starlette import status

from cloud.app.database import get_db
from cloud.app.repositories import (
    EventBusDefinitionsRepository,
    EventBusMessagesRepository,
    EventDeliveryLogRepository,
)
from cloud.app.services.platform_svc.redis_event_backend import RedisEventBackend
from cloud.app.services.platform_svc.sqlite_event_backend import SqliteEventBackend
from shared.base_service import BaseService

ALL_ENDS = ["cloud", "sales-coach", "sales-assistant", "assistant", "opportunity"]


def parse_targets(raw):
    """解析目标端列表，无效或空时返回全部端列表。"""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if parsed else ALL_ENDS.copy()
    except (json.JSONDecodeError, TypeError):
        return ALL_ENDS.copy()


class EventBusService(BaseService):
    """事件总线服务，管理事件定义、订阅、消息发布与投递。"""

    def __init__(self, db=Depends(get_db)):
        """初始化 EventBusService。"""
        super().__init__(db)
        self._backend = self._create_backend()

    def _create_backend(self):
        from shared.config import settings as app_cfg

        if app_cfg.REDIS_URL:
            return RedisEventBackend(app_cfg.REDIS_URL)
        return SqliteEventBackend()

    def create_definition(
        self,
        event_type: str,
        display_name: str,
        description: str,
        source_end: str,
        target_ends: list,
        schema_template: dict,
        priority: int,
    ) -> dict:
        """创建事件类型定义，重复类型名则返回 409 冲突。"""
        def_repo = EventBusDefinitionsRepository(self._connection())
        if def_repo.get_by_event_type(event_type):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Event type already exists")
        def_repo.create(
            {
                "event_type": event_type,
                "display_name": display_name,
                "description": description,
                "source_end": source_end,
                "target_ends": json.dumps(target_ends, ensure_ascii=False),
                "schema_template": json.dumps(schema_template, ensure_ascii=False),
                "priority": priority,
            }
        )
        return def_repo.get_by_event_type(event_type)

    def list_definitions(self, source_end: Optional[str] = None, enabled: Optional[int] = None) -> list:
        """查询事件定义列表，支持按来源端和启用状态筛选。"""
        return EventBusDefinitionsRepository(self._connection()).list_filtered(source_end=source_end, enabled=enabled)

    def toggle_definition(self, event_type: str) -> dict:
        """切换事件定义的启用/禁用状态。"""
        def_repo = EventBusDefinitionsRepository(self._connection())
        if not def_repo.get_by_event_type(event_type):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event definition not found")
        def_repo.toggle_enabled(event_type)
        return def_repo.get_by_event_type(event_type)

    def publish_message(
        self,
        event_type: str,
        source_entity_type: str,
        source_entity_id: str,
        payload: dict,
        correlation_id: str,
    ) -> dict:
        """发布事件消息，投递到目标端并标记为已送达。"""
        def_repo = EventBusDefinitionsRepository(self._connection())
        definition = def_repo.get_by_event_type(event_type)
        if not definition or not definition.get("enabled"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event type not found or disabled")
        msg_repo = EventBusMessagesRepository(self._connection())
        delivery_repo = EventDeliveryLogRepository(self._connection())
        message_id = f"evt:{uuid.uuid4()}"
        targets = parse_targets(definition["target_ends"])
        payload_json = json.dumps(payload, ensure_ascii=False)
        msg_repo.create(
            {
                "message_id": message_id,
                "event_type": event_type,
                "source_end": definition["source_end"],
                "source_entity_type": source_entity_type,
                "source_entity_id": source_entity_id,
                "payload": payload_json,
                "correlation_id": correlation_id,
                "priority": definition["priority"],
            }
        )
        results = self._backend.deliver(
            self.db,
            delivery_repo,
            message_id,
            targets,
            event_type,
            definition["source_end"],
            payload_json,
        )
        msg_repo.mark_delivered(message_id)
        return {
            "message": msg_repo.get_by_message_id(message_id),
            "delivery_results": results,
        }

    def list_messages(
        self,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        source_end: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list:
        """查询消息列表，支持按事件类型、状态、来源端和时间范围筛选。"""
        return EventBusMessagesRepository(self._connection()).list_filtered(
            event_type=event_type,
            status=status,
            source_end=source_end,
            start_date=start_date,
            end_date=end_date,
        )

    def get_message(self, message_id: str) -> dict:
        """获取单条消息详情及其投递日志。"""
        msg_repo = EventBusMessagesRepository(self._connection())
        msg = msg_repo.get_by_message_id(message_id)
        if not msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")
        logs = EventDeliveryLogRepository(self._connection()).list_by_message_id(message_id)
        return {"message": msg, "delivery_logs": logs}

    def redeliver_message(self, message_id: str) -> dict:
        """重新投递指定消息，重置其状态为待处理。"""
        msg_repo = EventBusMessagesRepository(self._connection())
        if not msg_repo.get_by_message_id(message_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")
        msg_repo.mark_pending_with_retry(message_id)
        EventDeliveryLogRepository(self._connection()).reset_pending_by_message(message_id)
        return msg_repo.get_by_message_id(message_id)

    def subscribe(self, target_end: str, event_types: list, callback_url: str = "") -> dict:
        """注册目标端的事件订阅。"""
        return self._backend.subscribe(target_end, event_types, callback_url)

    def list_delivery_log(
        self,
        message_id: Optional[str] = None,
        target_end: Optional[str] = None,
        delivery_status: Optional[str] = None,
    ) -> list:
        """查询投递日志，支持按消息 ID、目标端和状态筛选。"""
        return EventDeliveryLogRepository(self._connection()).list_filtered(
            message_id=message_id,
            target_end=target_end,
            delivery_status=delivery_status,
        )

    def get_dashboard(self) -> dict:
        """获取事件总线仪表盘，包含定义总数、消息统计与热门事件类型。"""
        def_repo = EventBusDefinitionsRepository(self._connection())
        msg_repo = EventBusMessagesRepository(self._connection())
        delivery_repo = EventDeliveryLogRepository(self._connection())
        msg_counts = msg_repo.count_by_status()
        delivery_counts = delivery_repo.count_by_status()
        overview = {
            "total_definitions": def_repo.count_all(),
            "total_messages": msg_repo.count_all(),
            "pending": msg_counts["pending"],
            "delivered": msg_counts["delivered"],
            "failed": msg_counts["failed"],
            "total_delivery_logs": delivery_repo.count_all(),
            "delivered_logs": delivery_counts["delivered"],
            "pending_logs": delivery_counts["pending"],
        }
        top_types = msg_repo.top_event_types(5)
        recent = msg_repo.list_recent(5)
        return {
            "overview": overview,
            "top_event_types": top_types,
            "recent_messages": recent,
        }


__all__ = ["EventBusService", "RedisEventBackend", "SqliteEventBackend"]
