"""竞品情报 API 路由。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.intel.competitor_tools import (
    PRODUCTS,
    _price_points,
    competitive_comparison,
    price_monitor,
    sentiment_analysis,
    strategy_suggestion,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/competitor", tags=["竞品情报"])

CRAWL_JOBS: dict[str, dict] = {}
BRIEFS: list[dict] = [
    {
        "id": "brief-001",
        "title": "竞品价格与舆情日报",
        "generated_at": "2026-06-09T09:00:00+08:00",
        "highlights": [
            "江苏价格波动维持在低位区间",
            "心血管品类社媒讨论量环比提升",
            "重点竞品准入覆盖保持稳定",
        ],
        "risk_level": "medium",
    }
]


class CrawlCreate(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=lambda: ["price", "social", "news"])
    max_pages: int = Field(10, ge=1, le=500)


class ProductCreate(BaseModel):
    id: Optional[str] = None
    name: str
    company: str
    category: str = ""
    indication: str = ""
    province_coverage: list[str] = Field(default_factory=list)
    status: str = "active"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    category: Optional[str] = None
    indication: Optional[str] = None
    province_coverage: Optional[list[str]] = None
    status: Optional[str] = None


class BriefGenerate(BaseModel):
    product_ids: list[str] = Field(default_factory=list)
    days: int = Field(7, ge=1, le=365)
    focus: str = "price_sentiment"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_product_ids(product_ids: str) -> list[str]:
    return [item.strip() for item in product_ids.split(",") if item.strip()]


def _price_trend(product_id: str, days: int) -> dict:
    monitored = price_monitor(product_id, "jiangsu")
    trend = _price_points(product_id, monitored["province"], days=days)
    return success(
        data={
            "product_id": product_id,
            "days": days,
            "currency": monitored["currency"],
            "province": monitored["province"],
            "trend": trend,
        }
    )


@router.post("/crawl", status_code=status.HTTP_201_CREATED, tags=["竞品情报"])
def create_crawl_job(body: CrawlCreate, _: dict = Depends(require_scope("visit"))):
    job_id = f"crawl-{uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "status": "running",
        "keywords": body.keywords,
        "sources": body.sources,
        "max_pages": body.max_pages,
        "progress": 12,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    CRAWL_JOBS[job_id] = job
    return success(data=job)


@router.get("/crawl/jobs", tags=["竞品情报"])
def list_crawl_jobs(current_user: dict = Depends(require_scope("visit"))):
    return success(data=list(CRAWL_JOBS.values()))


@router.delete("/crawl/{job_id}", tags=["竞品情报"])
def cancel_crawl_job(job_id: str, _: dict = Depends(require_scope("visit"))):
    job = CRAWL_JOBS.get(job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="crawl job not found")
    job["status"] = "cancelled"
    job["updated_at"] = _now_iso()
    return {"code": 0, "message": "success", "data": job}


@router.get("/crawl/status/{job_id}", tags=["竞品情报"])
def get_crawl_status(job_id: str, current_user: dict = Depends(require_scope("visit"))):
    job = CRAWL_JOBS.get(job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="crawl job not found")
    if job["status"] == "running":
        job["progress"] = min(100, job["progress"] + 28)
        job["status"] = "completed" if job["progress"] >= 100 else "running"
        job["updated_at"] = _now_iso()
    return {"code": 0, "message": "success", "data": job}


@router.get("/products", tags=["竞品情报"])
def list_products(status_filter: Optional[str] = Query(None, alias="status"), current_user: dict = Depends(require_scope("visit"))):
    products = list(PRODUCTS.values())
    if status_filter:
        products = [item for item in products if item["status"] == status_filter]
    return success(data=products)


@router.post("/products", status_code=status.HTTP_201_CREATED, tags=["竞品情报"])
def create_product(body: ProductCreate, _: dict = Depends(require_scope("visit"))):
    product_id = body.id or f"prod-{uuid4().hex[:6]}"
    if product_id in PRODUCTS:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="product already exists")
    product = body.model_dump()
    product["id"] = product_id
    PRODUCTS[product_id] = product
    return success(data=product)


@router.get("/products/{id}", tags=["竞品情报"])
def get_product(id: str, current_user: dict = Depends(require_scope("visit"))):
    product = PRODUCTS.get(id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    return {"code": 0, "message": "success", "data": product}


@router.put("/products/{id}", tags=["竞品情报"])
def update_product(id: str, body: ProductUpdate, _: dict = Depends(require_scope("visit"))):
    product = PRODUCTS.get(id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    updates = body.model_dump(exclude_none=True)
    product.update(updates)
    return success(data=product)


@router.delete("/products/{id}", tags=["竞品情报"])
def delete_product(id: str, _: dict = Depends(require_scope("visit"))):
    product = PRODUCTS.pop(id, None)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    return success(data={"deleted": id})


@router.get("/price/trend", tags=["竞品情报"])
def price_trend(product_id: str = Query(...), days: int = Query(90, ge=1, le=365), current_user: dict = Depends(require_scope("visit"))):
    return _price_trend(product_id, days)


@router.get("/price/anomaly", tags=["竞品情报"])
def price_anomaly(product_id: str = Query(...), current_user: dict = Depends(require_scope("visit"))):
    trend = _price_trend(product_id, 30).data["trend"]
    prices = [item["price"] for item in trend]
    average = sum(prices) / len(prices)
    anomalies = [
        {**item, "delta_pct": round((item["price"] - average) / average * 100, 2)} for item in trend if abs(item["price"] - average) / average >= 0.03
    ]
    return success(data={"product_id": product_id, "baseline_price": round(average, 2), "anomalies": anomalies})


@router.get("/sentiment", tags=["竞品情报"])
def sentiment(keyword: str = Query(...), days: int = Query(30, ge=1, le=365), current_user: dict = Depends(require_scope("visit"))):
    return success(data=sentiment_analysis(keyword, days))


@router.get("/volume", tags=["竞品情报"])
def volume(platform: str = Query("weibo"), current_user: dict = Depends(require_scope("visit"))):
    return success(
        data={
            "platform": platform,
            "series": [
                {"date": "2026-06-03", "mentions": 1280},
                {"date": "2026-06-04", "mentions": 1365},
                {"date": "2026-06-05", "mentions": 1492},
                {"date": "2026-06-06", "mentions": 1418},
                {"date": "2026-06-07", "mentions": 1586},
                {"date": "2026-06-08", "mentions": 1724},
                {"date": "2026-06-09", "mentions": 1688},
            ],
        }
    )


@router.get("/compare", tags=["竞品情报"])
def compare(product_ids: str = Query(..., description="逗号分隔产品ID，如 prod-001,prod-002"), current_user: dict = Depends(require_scope("visit"))):
    return success(data=competitive_comparison(_split_product_ids(product_ids)))


@router.get("/brief/latest", tags=["竞品情报"])
def latest_brief(current_user: dict = Depends(require_scope("visit"))):
    return success(data=BRIEFS[-1])


@router.get("/brief/{brief_id}", tags=["竞品情报"])
def get_brief(brief_id: str, current_user: dict = Depends(require_scope("visit"))):
    brief = next((item for item in BRIEFS if item["id"] == brief_id), None)
    if not brief:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="brief not found")
    return success(data=brief)


@router.post("/brief/generate", status_code=status.HTTP_201_CREATED, tags=["竞品情报"])
def generate_brief(body: BriefGenerate, _: dict = Depends(require_scope("visit"))):
    product_ids = body.product_ids or ["prod-001", "prod-002"]
    brief = {
        "id": f"brief-{uuid4().hex[:8]}",
        "title": "竞品情报自动简报",
        "generated_at": _now_iso(),
        "focus": body.focus,
        "days": body.days,
        "products": product_ids,
        "comparison": competitive_comparison(product_ids),
        "strategy": strategy_suggestion(product_ids[0], product_ids[1:]),
    }
    BRIEFS.append(brief)
    return success(data=brief)
