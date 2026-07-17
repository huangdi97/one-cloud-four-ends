"""KnowledgeWorkerAgent._detect_intent 单元测试 — 不需要 LLM/tool。"""

from __future__ import annotations

from cloud.app.agents.knowledge_worker_agent import KnowledgeWorkerAgent


class TestDetectIntent:
    def setup_method(self) -> None:
        self.agent = KnowledgeWorkerAgent()

    def test_detect_drug_info_by_medical_terms(self) -> None:
        assert self.agent._detect_intent("EGFR-TKI非小细胞肺癌") == "drug_info"

    def test_detect_clinical_guideline(self) -> None:
        assert self.agent._detect_intent("NSCLC一线治疗III期临床") == "clinical_guideline"

    def test_detect_competitive_intel(self) -> None:
        assert self.agent._detect_intent("竞品FDA上市") == "competitive_intel"

    def test_detect_hcp_profile(self) -> None:
        assert self.agent._detect_intent("张伟教授") == "hcp_profile"

    def test_detect_general_fallback(self) -> None:
        assert self.agent._detect_intent("你好") == "general"

    def test_priority_drug_over_guideline(self) -> None:
        assert self.agent._detect_intent("EGFR靶向药III期") == "drug_info"
