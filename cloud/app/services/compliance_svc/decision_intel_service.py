"""决策情报服务，负责决策案例的创建与AI辅助分析。"""

from typing import Optional

from fastapi import HTTPException
from starlette import status

from cloud.app.services.compliance_svc.decision_logger import DecisionLogger
from cloud.app.services.intel.intel_analyzer import IntelAnalyzer
from shared.base_service import BaseService


def _e404(name: str = "Resource"):
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"{name} not found")


class DecisionIntelService(BaseService):
    """决策情报服务，提供案例管理与AI辅助因果分析。"""

    def __init__(self, db=None):
        """初始化决策情报服务，注入日志器与分析器。"""
        super().__init__(db)
        self._logger = DecisionLogger(db)
        self._analyzer = IntelAnalyzer(db)

    def create_case(
        self,
        name: str,
        pipeline_run_id: Optional[int],
        description: str,
        outcome: str,
        outcome_score: float,
        context: dict,
        tags: list,
        uid: int,
    ) -> dict:
        """创建新的决策案例。"""
        return self._logger.create_case(name, pipeline_run_id, description, outcome, outcome_score, context, tags, uid)

    def list_cases(
        self,
        outcome_score_min: Optional[float] = None,
        outcome_score_max: Optional[float] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页列出决策案例，支持按评分、标签、关键词筛选。"""
        return self._logger.list_cases(outcome_score_min, outcome_score_max, tag, search, page, page_size)

    def get_case(self, case_id: int) -> dict:
        """获取指定决策案例的详情。"""
        return self._logger.get_case(case_id)

    def update_case(
        self,
        case_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        outcome: Optional[str] = None,
        outcome_score: Optional[float] = None,
        context: Optional[dict] = None,
        tags: Optional[list] = None,
    ) -> dict:
        """更新指定决策案例的字段。"""
        return self._logger.update_case(case_id, name, description, outcome, outcome_score, context, tags)

    def delete_case(self, case_id: int) -> None:
        """删除指定决策案例。"""
        return self._logger.delete_case(case_id)

    def analyze_case(self, case_id: int, custom_question: str, auth_header: str) -> dict:
        """对指定案例运行 AI 因果分析。"""
        return self._analyzer.analyze_case(case_id, custom_question, auth_header)

    def list_analyses(self, case_id: int) -> list:
        """列出某个案例的所有历史分析记录。"""
        return self._analyzer.list_analyses(case_id)

    def get_analysis(self, analysis_id: int) -> dict:
        """获取指定分析记录的详情。"""
        return self._analyzer.get_analysis(analysis_id)

    def reflect(self, filter_tags: list, max_cases: int, auth_header: str) -> dict:
        """跨案例反思，生成总结性洞察。"""
        return self._analyzer.reflect(filter_tags, max_cases, auth_header)

    def list_insights(
        self,
        insight_type: Optional[str] = None,
        confidence_min: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页列出洞察，支持按类型和置信度筛选。"""
        return self._logger.list_insights(insight_type, confidence_min, page, page_size)

    def get_insight(self, insight_id: int) -> dict:
        """获取指定洞察的详情。"""
        return self._logger.get_insight(insight_id)

    def update_insight(
        self,
        insight_id: int,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        confidence: Optional[float] = None,
        applicability: Optional[str] = None,
    ) -> dict:
        """更新指定洞察的字段。"""
        return self._logger.update_insight(insight_id, title, summary, confidence, applicability)

    def dashboard(self) -> dict:
        """获取决策情报仪表盘汇总数据。"""
        return self._logger.dashboard()
