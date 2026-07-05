"""Consolidated research matching router module.

Research product matching API endpoints — matches research products
against PI profiles (by research area) or free-text method
descriptions using keyword overlap scoring.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cloud.app.services.intel.research_service import ResearchService
from cloud.app.services.rep_workbench.product_matching_service import match_products_by_method, match_products_for_pi
from shared.auth import get_current_user
from shared.auth_scope import require_scope
from shared.base import success

matching_router = APIRouter(
    prefix="/api/research/matching",
    tags=["科研线"],
    dependencies=[Depends(require_scope("research"))],
)


class PiMatchRequest(BaseModel):
    """Request body: match products for a specific PI."""

    pi_id: int


class MethodMatchRequest(BaseModel):
    """Request body: match products by a free-text method description."""

    method_description: str


@matching_router.post("/for-pi", tags=["Research Matching"])
def match_for_pi(
    body: PiMatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Return top 3 product recommendations for a given PI profile."""
    results = match_products_for_pi(body.pi_id, top_k=3)
    ResearchService().log_audit(
        event_type="create",
        entity_type="matching",
        entity_id=body.pi_id,
        new_value=str(results),
        operator=current_user.get("username", ""),
    )
    return success(data=results)


@matching_router.post("/by-method", tags=["Research Matching"])
def match_by_method(
    body: MethodMatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Return top 3 product recommendations matching a method description."""
    results = match_products_by_method(body.method_description, top_k=3)
    ResearchService().log_audit(
        event_type="create",
        entity_type="matching",
        entity_id=0,
        new_value=f"method={body.method_description[:100]}",
        operator=current_user.get("username", ""),
    )
    return success(data=results)


# 科研 PI 路由：研究者搜索、详情、创建与审计日志。

from typing import Optional  # noqa: E402

from fastapi import APIRouter, Depends, HTTPException, Query  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from cloud.app.services.intel.research_pi_service import ResearchPiService  # noqa: E402
from shared.auth import get_current_user  # noqa: E402
from shared.auth_scope import require_scope  # noqa: E402

pi_router = APIRouter(
    prefix="/api/research/pi",
    tags=["科研线"],
    dependencies=[Depends(require_scope("research"))],
)


class PiCreate(BaseModel):
    """科研 PI 创建请求体。"""

    name: str
    institution: str
    department: str = ""
    title: str = ""
    hcp_id: Optional[int] = None
    research_areas: list[str] = []
    total_papers: int = 0
    total_grants: int = 0
    h_index: int = 0


@pi_router.get("/search", tags=["Research Pi"])
def search_pi(
    q: str = Query("", description="Search keyword"),
    current_user: dict = Depends(get_current_user),
):
    service = ResearchPiService()
    results = service.search(q)
    return success(data=results)


@pi_router.get("/{pi_id}", tags=["Research Pi"])
def get_pi(
    pi_id: int,
    current_user: dict = Depends(get_current_user),
):
    service = ResearchPiService()
    pi = service.get_by_id(pi_id)
    return success(data=pi)


@pi_router.post("", status_code=201, tags=["Research Pi"])
def create_pi(
    body: PiCreate,
    current_user: dict = Depends(get_current_user),
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    service = ResearchPiService()
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
    ResearchService().log_audit(
        event_type="create",
        entity_type="pi",
        entity_id=pi["pi_id"],
        new_value=str(pi),
        operator=current_user.get("username", ""),
    )
    return success(data=pi)


# 科研产品路由：产品搜索与详情查询。

from fastapi import APIRouter, Depends, Query  # noqa: E402

from cloud.app.services.intel.research_product_service import ResearchProductService  # noqa: E402
from shared.auth import get_current_user  # noqa: E402
from shared.auth_scope import require_scope  # noqa: E402

product_router = APIRouter(
    prefix="/api/research/products",
    tags=["科研线"],
    dependencies=[Depends(require_scope("research"))],
)


@product_router.get("/search", tags=["Research Product"])
def search_products(
    q: str = Query("", description="Search keyword"),
    category: str = Query("", description="Filter by category"),
    current_user: dict = Depends(get_current_user),
):
    service = ResearchProductService()
    results = service.search(q=q, category=category)
    return success(data=results)


@product_router.get("/{product_id}", tags=["Research Product"])
def get_product(
    product_id: int,
    current_user: dict = Depends(get_current_user),
):
    service = ResearchProductService()
    product = service.get_by_id(product_id)
    return success(data=product)


router = APIRouter()

router.include_router(matching_router)

router.include_router(pi_router)

router.include_router(product_router)

__all__ = ["router", "matching_router", "pi_router", "product_router"]
