"""事件总线路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from starlette import status

from cloud.app.event_bus_handlers import EventDefCreate, EventPublish, EventSubscribe
from cloud.app.services.platform_svc.event_bus_service import EventBusService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/events", tags=["Event Bus"])

ALL_ENDS = ["cloud", "sales-coach", "sales-assistant", "assistant", "opportunity"]


@router.post(
    "/definitions/create",
    status_code=status.HTTP_201_CREATED,
    summary="创建事件定义",
    description="创建一个新的事件定义，指定事件类型、来源端、目标端和优先级等。",
    tags=["Event Bus"],
)
def definitions_create(
    body: EventDefCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """创建一个新的事件定义。

    Args:
        body: 事件定义创建请求体。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含新事件定义的响应。
    """
    result = service.create_definition(
        event_type=body.event_type,
        display_name=body.display_name,
        description=body.description,
        source_end=body.source_end,
        target_ends=body.target_ends,
        schema_template=body.schema_template,
        priority=body.priority,
    )
    return success(data=result)


@router.get("/definitions/list", summary="查询事件定义列表", description="查询事件定义列表，可按来源端和启用状态进行筛选。", tags=["Event Bus"])
def definitions_list(
    source_end: Optional[str] = Query(None),
    enabled: Optional[int] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """查询事件定义列表，可按来源端和启用状态筛选。

    Args:
        source_end: 来源端筛选。
        enabled: 启用状态筛选（0/1）。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含事件定义列表的响应。
    """
    rows = service.list_definitions(source_end=source_end, enabled=enabled)
    return success(data=rows)


@router.patch("/definitions/{event_type}/toggle", summary="切换事件定义状态", description="切换指定事件定义的启用/禁用状态。", tags=["Event Bus"])
def definitions_toggle(
    event_type: str,
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """切换指定事件定义的启用/禁用状态。

    Args:
        event_type: 事件类型名称。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含更新后事件定义的响应。
    """
    result = service.toggle_definition(event_type)
    return success(data=result)


@router.post(
    "/messages/publish",
    status_code=status.HTTP_201_CREATED,
    summary="发布事件消息",
    description="发布一条事件消息到事件总线，指定事件类型、负载和关联 ID。",
    tags=["Event Bus"],
)
def messages_publish(
    body: EventPublish,
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """发布一条事件消息到总线。

    Args:
        body: 事件发布请求体。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含发布结果与消息 ID 的响应。
    """
    result = service.publish_message(
        event_type=body.event_type,
        source_entity_type=body.source_entity_type,
        source_entity_id=body.source_entity_id,
        payload=body.payload,
        correlation_id=body.correlation_id,
    )
    # EDAC: trigger subscribing agents
    try:
        from cloud.app.services.agent_ops.agent_event_bridge import on_event_published

        on_event_published(body.event_type, body.payload)
    except Exception:
        pass
    return success(data=result)


@router.get(
    "/messages/list", summary="查询事件消息列表", description="查询事件消息列表，支持按事件类型、状态、来源端和日期范围筛选。", tags=["Event Bus"]
)
def messages_list(
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source_end: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """查询事件消息列表，支持多种筛选条件。

    Args:
        event_type: 事件类型筛选。
        status: 消息状态筛选。
        source_end: 来源端筛选。
        start_date: 开始日期筛选。
        end_date: 结束日期筛选。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含消息列表的响应。
    """
    rows = service.list_messages(
        event_type=event_type,
        status=status,
        source_end=source_end,
        start_date=start_date,
        end_date=end_date,
    )
    return success(data=rows)


@router.get("/messages/{message_id}", summary="获取消息详情", description="根据消息 ID 获取指定事件消息的详细内容。", tags=["Event Bus"])
def messages_get(
    message_id: str,
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """获取指定事件消息的详情。

    Args:
        message_id: 消息 ID。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含消息数据的响应。
    """
    result = service.get_message(message_id)
    return success(data=result)


@router.post("/messages/{message_id}/redeliver", summary="重新投递消息", description="重新投递指定的事件消息到目标端。", tags=["Event Bus"])
def messages_redeliver(
    message_id: str,
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """重新投递指定的事件消息。

    Args:
        message_id: 消息 ID。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含重投结果的响应。
    """
    result = service.redeliver_message(message_id)
    return success(data=result)


@router.post(
    "/subscribe",
    status_code=status.HTTP_201_CREATED,
    summary="订阅事件",
    description="订阅指定类型的事件，配置目标端和回调地址。",
    tags=["Event Bus"],
)
def subscribe(
    body: EventSubscribe,
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """订阅指定类型的事件。

    Args:
        body: 订阅请求体，包含目标端和事件类型。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含订阅结果的响应。
    """
    result = service.subscribe(
        target_end=body.target_end,
        event_types=body.event_types,
        callback_url=body.callback_url,
    )
    return success(data=result)


@router.get("/delivery/log", summary="查询投递日志", description="查询事件投递日志，可按消息 ID、目标端和投递状态筛选。", tags=["Event Bus"])
def delivery_log_list(
    message_id: Optional[str] = Query(None),
    target_end: Optional[str] = Query(None),
    delivery_status: Optional[str] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """查询事件投递日志，可按消息、目标端和投递状态筛选。

    Args:
        message_id: 消息 ID 筛选。
        target_end: 目标端筛选。
        delivery_status: 投递状态筛选。
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含投递日志列表的响应。
    """
    rows = service.list_delivery_log(message_id=message_id, target_end=target_end, delivery_status=delivery_status)
    return success(data=rows)


@router.get("/dashboard", summary="事件总线仪表盘", description="获取事件总线仪表盘数据，包括消息量、投递成功率等统计。", tags=["Event Bus"])
def dashboard(
    current_user: dict = Depends(require_scope("visit")),
    service: EventBusService = Depends(),
):
    """获取事件总线仪表盘数据。

    Args:
        current_user: 当前认证用户。
        service: 事件总线服务实例。

    Returns:
        包含仪表盘数据的响应。
    """
    result = service.get_dashboard()
    return success(data=result)
