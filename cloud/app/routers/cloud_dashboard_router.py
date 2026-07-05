"""仪表盘概览路由。"""

from typing import Any

from fastapi import APIRouter, Depends

from cloud.app.services.rep_workbench.dashboard_service import DashboardService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", summary="仪表盘概览", description="获取仪表盘概览数据，包含关键指标汇总。", tags=["dashboard"])
def overview(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取仪表盘概览数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含概览数据的响应。
    """
    return success(data=service.get_overview())


@router.get("/users", summary="用户统计数据", description="获取平台用户统计数据，包括活跃用户、注册数等。", tags=["dashboard"])
def user_stats(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取用户统计数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含用户统计数据的响应。
    """
    return success(data=service.get_user_stats())


@router.get("/compliance", summary="合规统计数据", description="获取内容合规性统计数据，包括审核通过率等。", tags=["dashboard"])
def compliance_stats(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取合规统计数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含合规统计数据的响应。
    """
    return success(data=service.get_compliance_stats())


@router.get("/contents", summary="内容统计数据", description="获取内容管理统计数据，包括内容总量、分类分布等。", tags=["dashboard"])
def content_stats(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取内容统计数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含内容统计数据的响应。
    """
    return success(data=service.get_content_stats())


@router.get("/team/summary", summary="团队概览", description="获取团队工作概览汇总数据。", tags=["dashboard"])
def team_summary(
    current_user: dict = Depends(require_scope("visit")),
) -> Any:
    return success(data={})


@router.get("/team/ranking", summary="团队排名", description="获取团队成员工作绩效排名数据。", tags=["dashboard"])
def team_ranking(
    current_user: dict = Depends(require_scope("visit")),
) -> Any:
    return success(data={})


@router.get("/visit-trends", summary="拜访趋势", description="从visits表按日分组查最近30天拜访趋势，返回拜访日期与次数。", tags=["dashboard"])
def visit_trends(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取拜访趋势数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含拜访趋势数据的响应。
    """
    return success(data=service.get_visit_trends())


@router.get("/team-ranks", summary="团队排名", description="从teams表带用户关联查询团队排名，返回团队名称、评分与成员数。", tags=["dashboard"])
def team_ranks(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取团队排名数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含团队排名数据的响应。
    """
    return success(data=service.get_team_ranks())


@router.get(
    "/violations",
    summary="违规记录",
    description="从compliance_l2_log表查询违规记录，返回规则ID、名称、严重级别、详情和创建时间。",
    tags=["dashboard"],
)
def violations(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取违规记录数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含违规记录数据的响应。
    """
    return success(data=service.get_violations())


@router.get(
    "/research-kpis",
    summary="科研KPI",
    description="从research相关表(pi_profiles, products, quotations)查科研KPI，返回KPI名称与数值。",
    tags=["dashboard"],
)
def research_kpis(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取科研KPI数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含科研KPI数据的响应。
    """
    return success(data=service.get_research_kpis())


@router.get("/pi-sources", summary="PI来源统计", description="从pi_profiles表按source字段分组统计PI来源分布。", tags=["dashboard"])
def pi_sources(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取PI来源统计数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含PI来源统计数据的响应。
    """
    return success(data=service.get_pi_sources())


@router.get("/product-match-stats", summary="产品匹配统计", description="从product_matches表查匹配统计，返回各分类匹配概览。", tags=["dashboard"])
def product_match_stats(
    current_user: dict = Depends(require_scope("visit")),
    service: DashboardService = Depends(),
) -> Any:
    """获取产品匹配统计数据。

    Args:
        current_user: 当前认证用户。
        service: 仪表盘服务实例。

    Returns:
        包含产品匹配统计数据的响应。
    """
    return success(data=service.get_product_match_stats())
