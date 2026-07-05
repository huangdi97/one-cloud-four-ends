from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.rep_workbench.product_service import ProductService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductCreate(BaseModel):
    name: str
    category: str = ""
    brand: str = ""
    model: str = ""
    spec: str = ""
    unit_price: float = 0.0
    keywords: list[str] = []
    tech_params: dict = {}
    cert_status: str = ""


@router.get("/search", summary="搜索产品", description="根据关键词和分类搜索科研产品", tags=["products"])
def search_products(
    q: str = Query("", description="Search keyword"),
    category: str = Query("", description="Category filter"),
    _: dict = Depends(require_scope("research")),
    service: ProductService = Depends(),
):
    results = service.search(q=q, category=category)
    return success(data=results)


@router.get("/{product_id}", summary="产品详情", description="获取指定产品的详细信息", tags=["products"])
def get_product(
    product_id: int,
    _: dict = Depends(require_scope("research")),
    service: ProductService = Depends(),
):
    product = service.get_by_id(product_id)
    return success(data=product)


@router.post("", status_code=201, summary="创建产品", description="创建新的科研产品信息", tags=["products"])
def create_product(
    body: ProductCreate,
    _: dict = Depends(require_scope("research")),
    service: ProductService = Depends(),
):
    product = service.create(
        name=body.name,
        category=body.category,
        brand=body.brand,
        model=body.model,
        spec=body.spec,
        unit_price=body.unit_price,
        keywords=body.keywords,
        tech_params=body.tech_params,
        cert_status=body.cert_status,
    )
    return success(data=product)
