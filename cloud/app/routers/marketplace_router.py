"""市场与分析路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.collab.marketplace_service import MarketplaceService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/marketplace", tags=["Marketplace & Analytics"])


class MetricLog(BaseModel):
    agent_role: str
    metric_type: str
    metric_value: float
    metric_unit: str = ""
    period_start: str = ""
    period_end: str = ""


class BenchmarkGenerate(BaseModel):
    report_name: str
    report_type: str = ""
    period: str = ""


class MarketplacePublish(BaseModel):
    item_name: str
    description: str = ""
    agent_config: dict = {}
    category: str = ""
    price_model: str = "free"


@router.post("/metrics/log", status_code=status.HTTP_201_CREATED, tags=["Marketplace & Analytics"])
def log_metric(
    body: MetricLog,
    current_user: dict = Depends(require_scope("visit")),
    service: MarketplaceService = Depends(),
) -> Any:
    """记录代理指标数据。

    Args:
        body: 指标数据（角色、类型、值等）。

    Returns:
        记录成功的指标信息。
    """
    return success(
        data=service.log_metric(
            body.agent_role,
            body.metric_type,
            body.metric_value,
            body.metric_unit,
            body.period_start,
            body.period_end,
        )
    )


@router.get("/metrics/dashboard", tags=["Marketplace & Analytics"])
def metrics_dashboard(
    current_user: dict = Depends(require_scope("visit")),
    service: MarketplaceService = Depends(),
    agent_role: Optional[str] = Query(None),
) -> Any:
    """获取指标仪表盘数据。

    Args:
        agent_role: 按代理角色筛选。

    Returns:
        指标统计概览。
    """
    return success(data=service.metrics_dashboard(agent_role=agent_role))


@router.post("/benchmark/generate", status_code=status.HTTP_201_CREATED, tags=["Marketplace & Analytics"])
def generate_benchmark(
    body: BenchmarkGenerate,
    current_user: dict = Depends(require_scope("visit")),
    service: MarketplaceService = Depends(),
) -> Any:
    """生成基准报告。

    Args:
        body: 报告名称、类型、周期。

    Returns:
        生成的基准报告数据。
    """
    return success(data=service.generate_benchmark(body.report_name, body.report_type, body.period))


@router.get("/benchmark/list", tags=["Marketplace & Analytics"])
def list_benchmarks(
    current_user: dict = Depends(require_scope("visit")),
    service: MarketplaceService = Depends(),
    report_type: Optional[str] = Query(None),
) -> Any:
    """获取基准报告列表。

    Args:
        report_type: 按报告类型筛选。

    Returns:
        基准报告列表。
    """
    return success(data=service.list_benchmarks(report_type=report_type))


@router.post("/items/publish", status_code=status.HTTP_201_CREATED, tags=["Marketplace & Analytics"])
def publish_item(
    body: MarketplacePublish,
    current_user: dict = Depends(require_scope("visit")),
    service: MarketplaceService = Depends(),
) -> Any:
    """发布代理商品到市场。

    Args:
        body: 商品信息（名称、描述、配置等）。

    Returns:
        发布后的商品信息。
    """
    return success(
        data=service.publish_item(
            body.item_name,
            body.description,
            body.agent_config,
            body.category,
            body.price_model,
            str(current_user.get("sub", "unknown")),
        )
    )


@router.get("/items/discover", tags=["Marketplace & Analytics"])
def discover_items(
    current_user: dict = Depends(require_scope("visit")),
    service: MarketplaceService = Depends(),
    category: Optional[str] = Query(None),
    price_model: Optional[str] = Query(None),
    enabled: Optional[int] = Query(None),
) -> Any:
    """发现市场商品列表。

    Args:
        category: 按分类筛选。
        price_model: 按定价模式筛选。
        enabled: 按启用状态筛选。

    Returns:
        可发现的商品列表。
    """
    return success(data=service.discover_items(category=category, price_model=price_model, enabled=enabled))
