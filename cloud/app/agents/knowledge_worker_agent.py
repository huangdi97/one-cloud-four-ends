"""KnowledgeWorkerAgent — RAG增强的知识问答Agent，支持多领域知识检索与LLM合成。"""

from __future__ import annotations

import logging
from typing import Any

from cloud.app.agent_runtime.core.models import AgentIdentity
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

_CONFIDENCE_LLM_WITH_KB = 0.85
_CONFIDENCE_LLM_NO_KB = 0.4
_CONFIDENCE_LLM_ERROR = 0.3
_CONFIDENCE_NO_LLM = 0.5

_INTENT_KEYWORDS = {
    "hcp_profile": ["医生", "HCP", "专家", "主任", "医师", "教授"],
    "drug_info": ["药品", "药物", "剂量", "适应症", "用法", "禁忌", "EGFR", "TKI", "PD-1", "PD-L1", "靶向", "化疗", "单抗", "抑制剂"],
    "competitive_intel": ["竞品", "竞争对手", "市场份额", "对标", "NDA", "FDA", "NMPA", "上市"],
    "clinical_guideline": ["指南", "共识", "临床路径", "标准", "一线", "二线", "推荐", "PFS", "OS", "ORR", "NCCN", "CSCO", "III期", "II期", "I期"],
}

__all__ = ["KnowledgeWorkerAgent"]


class KnowledgeWorkerAgent(BaseAgent):
    """RAG增强的知识问答Agent，多领域知识检索+LLM合成。"""

    def __init__(
        self,
        identity: AgentIdentity = None,
        vector_memory: Any = None,
        llm_service: Any = None,
        tool_bridge: Any = None,
    ) -> None:
        self._identity = identity
        self._vm = vector_memory
        self._llm = llm_service
        self._tools = tool_bridge
        self._intents = list(_INTENT_KEYWORDS.keys()) + ["general"]

    async def execute(self, context: AgentContext) -> AgentResponse:
        agent_id = self._identity.key if self._identity else "unknown"
        logger.info("%s execute: %s", agent_id, context.message[:64])
        msg = context.message
        intent = self._detect_intent(msg)
        sources = []
        if self._vm is not None:
            try:
                results = self._vm.hybrid_search(agent_name="knowledge_worker", query=msg, top_k=5, cross_agent=True)
                sources = results
            except Exception:
                logger.exception("Vector memory search failed")

        context_text = self._build_context(sources)
        empty_kb = not sources
        prompt = self._build_prompt(intent, msg, context_text, empty_kb)
        reply = ""
        confidence = 0.0
        if self._llm is not None and context_text:
            try:
                reply = await self._llm.generate(prompt)
                confidence = _CONFIDENCE_LLM_WITH_KB
            except Exception:
                logger.exception("LLM generate failed")
                reply = self._fallback_reply(intent, sources)
                confidence = _CONFIDENCE_LLM_ERROR
        elif self._llm is not None:
            reply = self._fallback_reply(intent, sources)
            confidence = _CONFIDENCE_LLM_NO_KB
        else:
            reply = self._fallback_reply(intent, sources)
            confidence = _CONFIDENCE_NO_LLM

        actions = [{"agent": "knowledge_worker", "intent": intent, "confidence": confidence}]
        return AgentResponse(reply=reply, actions=actions, memory_updates=[])

    def _default_capabilities(self) -> list[str]:
        return ["knowledge_retrieval", "rag_query", "semantic_search"]

    def _detect_intent(self, msg: str) -> str:
        """通过关键词匹配检测用户问题的知识领域意图。"""
        _PRIORITY = ["drug_info", "clinical_guideline", "competitive_intel", "hcp_profile", "general"]
        matched = []
        for intent, keywords in _INTENT_KEYWORDS.items():
            if any(kw in msg for kw in keywords):
                matched.append(intent)
        if not matched:
            return "general"
        for intent in _PRIORITY:
            if intent in matched:
                return intent
        return "general"

    def _build_context(self, sources: list) -> str:
        """将向量检索结果组装为带来源标注的上下文文本。"""
        if not sources:
            return ""
        parts = ["相关知识："]
        for s in sources:
            content = s.get("content", "")[:500]
            meta = s.get("metadata", {})
            source = s.get("source_agent", "unknown")
            parts.append(f"[来源:{source}] {content}")
            if meta:
                parts.append(f"  元数据: {meta}")
        return "\n".join(parts)

    def _build_prompt(self, intent: str, msg: str, context: str, empty: bool) -> str:
        """根据意图和知识库上下文构造LLM提示词。"""
        empty_note = "\n注意：当前知识库为空，请基于自身知识回答，并在回复末尾标注'当前知识库为空'。" if empty else ""
        return f"你是一个医药行业知识助手，当前查询意图：{intent}。\n用户问题：{msg}\n{context}{empty_note}\n请用中文给出专业、准确的回答。"

    def _fallback_reply(self, intent: str, sources: list) -> str:
        """LLM不可用时根据知识库是否为空返回兜底回复。"""
        if not sources:
            return "当前知识库为空，无法检索到相关信息。请稍后再试或联系管理员导入知识数据。"
        return "已检索到相关知识，但LLM服务暂不可用。请稍后重试。"
