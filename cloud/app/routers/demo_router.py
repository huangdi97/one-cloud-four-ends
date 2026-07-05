from fastapi import APIRouter, Depends

from cloud.app.compliance.service import ComplianceService
from cloud.app.services.rep_workbench.dashboard_service import DashboardService
from shared.base import success

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/dashboard", summary="仪表盘概览", description="获取演示仪表盘的整体概览数据", tags=["demo"])
def dashboard_overview(service: DashboardService = Depends()):
    return success(data=service.get_overview())


@router.get("/dashboard/users", summary="用户统计", description="获取演示仪表盘的用户统计数据", tags=["demo"])
def dashboard_users(service: DashboardService = Depends()):
    return success(data=service.get_user_stats())


@router.get("/dashboard/compliance", summary="合规统计", description="获取演示仪表盘的合规统计数据", tags=["demo"])
def dashboard_compliance(service: DashboardService = Depends()):
    return success(data=service.get_compliance_stats())


@router.get("/compliance/summary", summary="合规摘要", description="获取合规摘要数据", tags=["demo"])
def compliance_summary(service: ComplianceService = Depends()):
    return success(data=service.dashboard_summary())


@router.get("/visit-trends", summary="拜访趋势", description="获取拜访趋势数据", tags=["demo"])
def visit_trends(service: DashboardService = Depends()):
    return success(data=service.get_visit_trends())


@router.get("/team-ranks", summary="团队排名", description="获取团队排名数据", tags=["demo"])
def team_ranks(service: DashboardService = Depends()):
    return success(data=service.get_team_ranks())


@router.get("/violations", summary="违规记录", description="获取违规记录数据", tags=["demo"])
def violations(service: DashboardService = Depends()):
    return success(data=service.get_violations())


@router.get("/research-kpis", summary="科研KPI", description="获取科研KPI数据", tags=["demo"])
def research_kpis(service: DashboardService = Depends()):
    return success(data=service.get_research_kpis())


@router.get("/pi-sources", summary="PI来源", description="获取PI来源数据", tags=["demo"])
def pi_sources(service: DashboardService = Depends()):
    return success(data=service.get_pi_sources())


@router.get("/product-match-stats", summary="产品匹配统计", description="获取产品匹配统计数据", tags=["demo"])
def product_match_stats(service: DashboardService = Depends()):
    return success(data=service.get_product_match_stats())
