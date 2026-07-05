"""Agent 实体 — 从 identity.yaml 加载并持有运行时组件引用。"""

from cloud.app.agent_runtime.core.agent_analysis import AgentAnalysis
from cloud.app.agent_runtime.core.agent_autonomous import AgentAutonomous
from cloud.app.agent_runtime.core.agent_core import AgentCore


class Agent(AgentAnalysis, AgentAutonomous, AgentCore):
    pass
