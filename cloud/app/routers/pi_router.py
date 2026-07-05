"""PI 路由：研究者信息搜索、详情、创建与更新。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.intel.pi_service import PiService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/pi", tags=["pi"])


class PiCreate(BaseModel):
    """PI 创建请求体。"""

    name: str
    institution: str
    department: str = ""
    title: str = ""
    hcp_id: Optional[int] = None
    research_areas: list[str] = []
    total_papers: int = 0
    total_grants: int = 0
    h_index: int = 0


class PiUpdate(BaseModel):
    """PI 更新请求体。"""

    name: Optional[str] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    hcp_id: Optional[int] = None
    research_areas: Optional[list[str]] = None
    total_papers: Optional[int] = None
    total_grants: Optional[int] = None
    h_index: Optional[int] = None


@router.get("/search", summary="搜索PI", description="根据关键词搜索研究者信息", tags=["pi"])
def search_pi(
    q: str = Query("", description="Search keyword"),
    _: dict = Depends(require_scope("research")),
    service: PiService = Depends(),
):
    results = service.search(q)
    return success(data=results)


@router.get("/{pi_id}", summary="PI详情", description="获取指定研究者的详细信息", tags=["pi"])
def get_pi(
    pi_id: int,
    _: dict = Depends(require_scope("research")),
    service: PiService = Depends(),
):
    pi = service.get_by_id(pi_id)
    return success(data=pi)


@router.post("", status_code=201, summary="创建PI", description="创建新的研究者信息", tags=["pi"])
def create_pi(
    body: PiCreate,
    _: dict = Depends(require_scope("research")),
    service: PiService = Depends(),
):
    pi = service.create(
        name=body.name,
        institution=body.institution,
        department=body.department,
        title=body.title,
        hcp_id=body.hcp_id,
        research_areas=body.research_areas,
        total_papers=body.total_papers,
        total_grants=body.total_grants,
        h_index=body.h_index,
    )
    return success(data=pi)


@router.put("/{pi_id}", summary="更新PI", description="更新指定研究者的信息", tags=["pi"])
def update_pi(
    pi_id: int,
    body: PiUpdate,
    _: dict = Depends(require_scope("research")),
    service: PiService = Depends(),
):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    pi = service.update(pi_id, **kwargs)
    return success(data=pi)
