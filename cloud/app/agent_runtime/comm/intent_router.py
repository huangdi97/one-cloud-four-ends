"""IntentRouter — 语义向量相似度路由 + LLM 兜底。"""

import logging
import math
import re
from collections import Counter

from cloud.app.agent_runtime.runtime_llm import RuntimeLLM

logger = logging.getLogger(__name__)

_INTENTS = {
    "compliance_query": {
        "target_agent": "compliance_monitor",
        "utterances": [
            "查一下华北区最近的合规风险",
            "最近的合规评分怎么样",
            "有没有新的合规违规记录",
            "这个月的合规检查结果",
            "合规方面有什么异常",
            "哪些代表有合规问题",
            "合规风险最高的地区是哪里",
            "最近的合规审计结果",
            "合规评分下降的原因是什么",
            "有没有接到合规投诉",
            "合规方面的红灯预警有哪些",
            "最新的合规政策变更",
            "这个季度的合规报告",
            "检查一下合规数据",
            "合规异常处理进度",
        ],
    },
    "visit_schedule": {
        "target_agent": "suggestion_agent",
        "utterances": [
            "帮我排明天的拜访",
            "今天要去拜访哪个医生",
            "安排一下下周的拜访计划",
            "这周还有哪些医生需要拜访",
            "拜访路线怎么规划",
            "帮我约一下张主任的拜访",
            "明天拜访安排是什么",
            "这个月的拜访计划",
            "哪些高价值客户需要拜访",
            "拜访优先级怎么排",
            "帮我看看拜访记录",
            "最近的拜访效果怎么样",
            "有哪些医生好久没拜访了",
            "安排一次重点客户的拜访",
            "拜访日程帮我整理一下",
        ],
    },
    "competitor_intel": {
        "target_agent": "competitor_crawler",
        "utterances": [
            "竞品C最近有什么新动态",
            "查一下竞争对手的最新消息",
            "竞品获批了什么新适应症",
            "竞品市场活动有哪些",
            "竞品最新的价格调整",
            "竞争对手在做什么",
            "竞品最近有什么大动作",
            "查一下竞品的临床试验进展",
            "竞品销售策略是什么",
            "竞品和我们对比的优势劣势",
            "最近竞品有什么新产品上市",
            "竞品在华北区的活动情况",
            "竞争对手的团队规模",
            "竞品医保准入情况",
            "竞品最新的学术会议动态",
        ],
    },
    "expense_check": {
        "target_agent": "audit_agent",
        "utterances": [
            "查一下最近的费用报销",
            "这个月的费用支出明细",
            "费用有没有异常",
            "超预算的费用有哪些",
            "查一下张三的报销记录",
            "费用审计结果怎么样",
            "最近的差旅费用",
            "哪个代表的费用最高",
            "费用合规性检查",
            "费用报销审批进度",
            "这个季度的费用分析",
            "费用支出趋势",
            "异常费用预警",
            "市场活动费用明细",
            "费用预算执行情况",
        ],
    },
    "data_analysis": {
        "target_agent": "knowledge_worker",
        "utterances": [
            "帮我分析一下销售数据",
            "最近的销售趋势怎么样",
            "数据的异常点有哪些",
            "做个数据分析报表",
            "分析一下这个季度的业绩",
            "数据对比分析",
            "销售数据的同比环比",
            "按地区分析销售情况",
            "产品线的数据分析",
            "数据分析结果导出",
            "帮我查一下知识库",
            "搜索一下相关的资料",
            "最新的行业数据",
            "市场数据分析报告",
            "客户数据的分析结果",
        ],
    },
    "voice_input": {
        "target_agent": "asr_agent",
        "utterances": [
            "帮我语音输入一下",
            "语音转文字",
            "记录一下我说的内容",
            "语音指令",
            "我说的你记下来",
        ],
    },
}

_SOFTMAX_SCALE = 12.0
_CONFIDENCE_THRESHOLD = 0.85


def _char_bigrams(text: str) -> Counter:
    text = re.sub(r"\s+", "", text.lower())
    return Counter(text[i : i + 2] for i in range(len(text) - 1))


def _cosine_similarity(v1: Counter, v2: Counter) -> float:
    common = set(v1) & set(v2)
    dot = sum(v1[x] * v2[x] for x in common)
    norm1 = sum(v * v for v in v1.values()) ** 0.5
    norm2 = sum(v * v for v in v2.values()) ** 0.5
    if not norm1 or not norm2:
        return 0.0
    return dot / (norm1 * norm2)


class IntentRouter:
    """语义 intent 路由：字符 bigram 余弦相似度 + softmax 置信度 + LLM 兜底。"""

    def __init__(self):
        self._llm = RuntimeLLM()
        self._centroids: dict[str, Counter] = {}
        self._targets: dict[str, str] = {}
        self._build_index()

    def _build_index(self):
        for intent_name, intent_data in _INTENTS.items():
            centroid = Counter()
            for utterance in intent_data["utterances"]:
                centroid += _char_bigrams(utterance)
            self._centroids[intent_name] = centroid
            self._targets[intent_name] = intent_data["target_agent"]

    def route(self, text: str) -> tuple[str, float, str | None]:
        """基于 bigram 余弦相似度 + softmax 路由用户输入到目标 Agent。"""
        text_vec = _char_bigrams(text)
        if not text_vec:
            return ("ambiguous", 0.0, None)

        raw_scores = {name: _cosine_similarity(text_vec, centroid) for name, centroid in self._centroids.items()}
        best_intent = max(raw_scores, key=raw_scores.get)

        exp_scores = {name: math.exp(raw * _SOFTMAX_SCALE) for name, raw in raw_scores.items()}
        exp_total = sum(exp_scores.values())
        confidence = exp_scores[best_intent] / exp_total if exp_total > 0 else 0.0
        if confidence > _CONFIDENCE_THRESHOLD:
            return (best_intent, confidence, self._targets.get(best_intent))
        return ("ambiguous", confidence, None)

    def llm_fallback(self, text: str) -> tuple[str, float, str | None]:
        """LLM 兜底分类，当语义路由置信度不足时使用。"""
        prompt = [
            {
                "role": "system",
                "content": (
                    "你是一个意图分类器。请将用户输入分类到以下意图之一：\n"
                    "  - compliance_query: 合规查询、风险检查\n"
                    "  - visit_schedule: 拜访排程、日程管理\n"
                    "  - competitor_intel: 竞品情报、竞争对手\n"
                    "  - expense_check: 费用审计、报销查询\n"
                    "  - data_analysis: 数据分析、知识检索\n"
                    "  - voice_input: 语音输入\n"
                    "只需返回意图名称，不要其它文字。"
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            result = self._llm._call_ai(prompt, temperature=0.0)
            intent = result.get("response", "").strip().lower()
            if intent in self._targets:
                return (intent, 0.9, self._targets[intent])
        except Exception:
            logger.exception("LLM fallback intent classification failed")
        return ("ambiguous", 0.0, None)
