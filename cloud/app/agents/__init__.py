"""Agent 核心模块 — 仓库、抽象基类与具体实现。"""

from cloud.app.agent_runtime.core.models import AgentIdentity
from cloud.app.agents.agent_repository import AgentRepository
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent
from cloud.app.agents.edac_agent_trigger import EdacAgentTrigger
from cloud.app.agents.model_router import ModelRouter, RouteResult
from cloud.app.agents.specialized_agent import SpecializedAgent

try:
    from cloud.app.agents.competitor_crawler_agent import CompetitorCrawlerAgent
except ImportError:
    CompetitorCrawlerAgent = None  # type: ignore

try:
    from cloud.app.agents.knowledge_worker_agent import KnowledgeWorkerAgent
except ImportError:
    KnowledgeWorkerAgent = None  # type: ignore

try:
    from cloud.app.agents.opportunity_scanner_agent import OpportunityScannerAgent
except ImportError:
    OpportunityScannerAgent = None  # type: ignore

try:
    from cloud.app.agents.sales_coach_analyst_agent import SalesCoachAnalystAgent
except ImportError:
    SalesCoachAnalystAgent = None  # type: ignore

__all__ = [
    "AgentRepository",
    "AgentContext",
    "AgentResponse",
    "BaseAgent",
    "EdacAgentTrigger",
    "ModelRouter",
    "RouteResult",
    "SpecializedAgent",
    "AgentIdentity",
    "CompetitorCrawlerAgent",
    "KnowledgeWorkerAgent",
    "OpportunityScannerAgent",
    "SalesCoachAnalystAgent",
]
