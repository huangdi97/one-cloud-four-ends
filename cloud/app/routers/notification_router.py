"""通知管理路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.database import get_db
from cloud.app.services.rep_workbench.notification_service import NotificationService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/notifications", tags=["notifications"])


class TemplateCreate(BaseModel):
    name: str
    title_template: str
    body_template: str
    category: str


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    title_template: Optional[str] = None
    body_template: Optional[str] = None
    category: Optional[str] = None


class NotificationSend(BaseModel):
    user_id: int
    template_name: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    context: Optional[dict] = None
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None


@router.post("/templates", status_code=status.HTTP_201_CREATED, tags=["notifications"])
def create_template(
    body: TemplateCreate,
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """创建通知模板。Args: body 模板信息. Returns: 创建的模板."""
    service = NotificationService(db=db)
    result = service.create_template(
        name=body.name,
        title_template=body.title_template,
        body_template=body.body_template,
        category=body.category,
    )
    return success(data=result)


@router.get("/templates", tags=["notifications"])
def list_templates(
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """获取所有通知模板列表。Returns: 模板列表."""
    service = NotificationService(db=db)
    return success(data=service.list_templates())


@router.get("/templates/{template_id}", tags=["notifications"])
def get_template(
    template_id: int,
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """获取指定通知模板详情。Args: template_id 模板ID. Returns: 模板详情."""
    service = NotificationService(db=db)
    return success(data=service.get_template(template_id))


@router.patch("/templates/{template_id}", tags=["notifications"])
def update_template(
    template_id: int,
    body: TemplateUpdate,
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """更新通知模板。Args: template_id 模板ID; body 更新字段. Returns: 更新后的模板."""
    service = NotificationService(db=db)
    updates = {}
    for field in ("name", "title_template", "body_template", "category"):
        val = getattr(body, field, None)
        if val is not None:
            updates[field] = val
    result = service.update_template(template_id, **updates)
    return success(data=result)


@router.delete("/templates/{template_id}", tags=["notifications"])
def delete_template(
    template_id: int,
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """删除通知模板。Args: template_id 模板ID."""
    service = NotificationService(db=db)
    service.delete_template(template_id)
    return success()


@router.post("/send", status_code=status.HTTP_201_CREATED, tags=["notifications"])
def send_notification(
    body: NotificationSend,
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """发送通知。Args: body 发送参数. Returns: 发送结果."""
    service = NotificationService(db=db)
    result = service.send(
        user_id=body.user_id,
        template_name=body.template_name,
        title=body.title,
        body=body.body,
        category=body.category,
        context=body.context,
        ref_type=body.ref_type,
        ref_id=body.ref_id,
    )
    return success(data=result)


@router.get("/", tags=["notifications"])
def list_notifications(
    is_read: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """获取当前用户的通知列表。Args: is_read 是否已读; page/page_size 分页. Returns: 通知列表."""
    service = NotificationService(db=db)
    user_id = int(current_user["sub"])
    result = service.list_notifications(user_id=user_id, is_read=is_read, page=page, page_size=page_size)
    return success(data=result)


@router.patch("/{notification_id}/read", tags=["notifications"])
def mark_read(
    notification_id: int,
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """标记通知为已读。Args: notification_id 通知ID. Returns: 更新结果."""
    service = NotificationService(db=db)
    user_id = int(current_user["sub"])
    result = service.mark_read(notification_id, user_id)
    return success(data=result)


@router.get("/unread-count", tags=["notifications"])
def unread_count(
    current_user: dict = Depends(require_scope("visit")),
    db=Depends(get_db),
) -> Any:
    """获取当前用户未读通知数量。Returns: 未读数."""
    service = NotificationService(db=db)
    user_id = int(current_user["sub"])
    return success(data=service.unread_count(user_id))
