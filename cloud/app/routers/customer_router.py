"""客户管理路由。"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.rep_workbench.customer_service import CustomerService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str = ""
    hospital: str = ""
    department: str = ""
    specialty: str = ""
    phone: str = Field("", max_length=20)
    email: str = Field("", max_length=100)
    tags: List[str] = []


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    specialty: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    status: Optional[str] = None


@router.post(
    "/", status_code=status.HTTP_201_CREATED, summary="创建客户", description="创建一个新的客户记录，包含姓名、医院、科室等信息。", tags=["customers"]
)
def create_customer(
    body: CustomerCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: CustomerService = Depends(),
) -> Any:
    """创建客户。"""
    user_id = int(current_user["sub"])
    row = service.create_customer(
        name=body.name,
        title=body.title,
        hospital=body.hospital,
        department=body.department,
        specialty=body.specialty,
        phone=body.phone,
        email=body.email,
        tags=body.tags,
        user_id=user_id,
    )
    return success(data=row)


@router.get("/", summary="查询客户列表", description="分页查询客户列表，支持按姓名、医院、科室和状态筛选。", tags=["customers"])
def list_customers(
    name: str = Query(None),
    hospital: str = Query(None),
    department: str = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: CustomerService = Depends(),
) -> Any:
    """分页查询客户列表。"""
    result = service.list_customers(
        name=name,
        hospital=hospital,
        department=department,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get("/{customer_id}", summary="获取客户详情", description="根据客户 ID 获取单个客户的详细信息。", tags=["customers"])
def get_customer(
    customer_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: CustomerService = Depends(),
) -> Any:
    """获取客户详情。"""
    row = service.get_customer(customer_id)
    return success(data=row)


@router.patch("/{customer_id}", summary="更新客户信息", description="部分更新指定客户的信息，如姓名、联系方式、标签或状态。", tags=["customers"])
def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: CustomerService = Depends(),
) -> Any:
    """更新客户信息。"""
    row = service.update_customer(
        customer_id=customer_id,
        name=body.name,
        title=body.title,
        hospital=body.hospital,
        department=body.department,
        specialty=body.specialty,
        phone=body.phone,
        email=body.email,
        tags=body.tags,
        status=body.status,
    )
    return success(data=row)


@router.delete("/{customer_id}", summary="删除客户", description="根据客户 ID 删除指定的客户记录。", tags=["customers"])
def delete_customer(
    customer_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: CustomerService = Depends(),
) -> Any:
    """删除客户。"""
    service.delete_customer(customer_id)
    return success()
