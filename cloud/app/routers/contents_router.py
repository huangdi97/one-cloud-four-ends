"""内容管理路由。"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.rep_workbench.content_service import ContentService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/contents", tags=["contents"])


class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    category: str
    tags: List[str] = []


class ContentResponse(BaseModel):
    id: int
    title: str
    body: str
    category: str
    tags: str
    status: str
    compliance_score: Optional[float] = None
    created_by: int
    created_at: str
    updated_at: str


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class PaginatedContents(BaseModel):
    items: List[ContentResponse]
    total: int
    page: int
    page_size: int


@router.post(
    "/", status_code=status.HTTP_201_CREATED, summary="创建内容", description="创建一个新的内容条目，包含标题、正文、分类和标签。", tags=["contents"]
)
def create_content(
    body: ContentCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: ContentService = Depends(),
) -> Any:
    """创建内容。"""
    user_id = int(current_user["sub"])
    row = service.create_content(body.title, body.body, body.category, body.tags, user_id)
    return success(data=row)


@router.get("/", summary="列出内容", description="分页查询内容列表，支持按状态和分类筛选。", tags=["contents"])
def list_contents(
    status_param: str = Query(None, alias="status"),
    category: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: ContentService = Depends(),
) -> Any:
    """分页列出内容。"""
    result = service.list_contents(
        status_filter=status_param,
        category_filter=category,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get("/{content_id:int}", summary="获取内容详情", description="根据内容 ID 获取单个内容的详细信息。", tags=["contents"])
def get_content(
    content_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: ContentService = Depends(),
) -> Any:
    """获取内容详情。"""
    row = service.get_content(content_id)
    return success(data=row)


@router.patch("/{content_id:int}", summary="更新内容", description="部分更新指定内容的信息，如标题、正文、分类、标签或状态。", tags=["contents"])
def update_content(
    content_id: int,
    body: ContentUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: ContentService = Depends(),
) -> Any:
    """更新内容。"""
    row = service.update_content(
        content_id,
        title=body.title,
        body=body.body,
        category=body.category,
        tags=body.tags,
        status_field=body.status,
    )
    return success(data=row)


@router.delete("/{content_id:int}", summary="删除内容", description="根据内容 ID 删除指定的内容条目。", tags=["contents"])
def delete_content(
    content_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: ContentService = Depends(),
) -> Any:
    """删除内容。"""
    service.delete_content(content_id)
    return success()
