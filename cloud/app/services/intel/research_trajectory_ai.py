"""科研轨迹 AI 预测模块，负责构建 LLM 提示词、调用 AI 网关并解析预测结果。"""

import json
import logging

from cloud.app.services.agent_ops.ai_gateway_service import AiGatewayService
from shared.config import settings

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK = {
    "predicted_areas": [],
    "confidence": 0.0,
    "rationale": "AI预测不可用，降级至规则逻辑",
    "transition_path": [],
    "key_turning_points": [],
}


def build_prediction_prompt(pi_info: dict, time_series_features: dict, horizon_days: int) -> str:
    """构建 AI 预测提示词。"""
    n = time_series_features["stat_features"]["observation_count"]
    tc = time_series_features["stat_features"]["transition_count"]
    stability = time_series_features["stat_features"]["latest_stability_measure"]

    areas_summary = []
    for area, weights in time_series_features["area_weights_series"].items():
        vals = [w["weight"] for w in weights]
        areas_summary.append(
            {
                "area": area,
                "value_count": len(vals),
                "recent_weight": vals[-1] if vals else 0,
            }
        )

    transitions_summary = []
    for t in time_series_features["dominant_transitions"]:
        transitions_summary.append(
            {
                "from": t["from_area"],
                "to": t["to_area"],
                "interval_days": t["interval_days"],
            }
        )

    event_count = len(time_series_features["event_timeline"])

    prompt = f"""你是一个科研领域转移预测专家。根据以下PI历史轨迹特征，预测未来{horizon_days}天内的领域变化。

## PI基本信息
- 姓名: {pi_info.get("name", "未知")}
- 机构: {pi_info.get("institution", "未知")}
- 职称: {pi_info.get("title", "未知")}
- 研究方向: {pi_info.get("research_areas", "未知")}

## 时序统计
- 轨迹点数量: {n}
- 领域转移次数: {tc}
- 稳定度: {stability}
- 报价/询价事件数: {event_count}

## 领域权重摘要
{json.dumps(areas_summary, ensure_ascii=False, indent=2)}

## 历史领域转移记录
{json.dumps(transitions_summary, ensure_ascii=False, indent=2)}

请按以下JSON格式返回预测结果（只返回JSON，不要其他文字）：
{{
  "predicted_areas": [{{"area": "领域名称", "probability": 0.0~1.0, "trend": "up/down/stable", "driver": "驱动因素简述"}}],
  "confidence": 0.0~1.0,
  "rationale": "推理过程简述",
  "transition_path": ["当前领域", "预测领域1", "预测领域2"],
  "key_turning_points": ["关键转折点描述"]
}}"""
    return prompt


def call_llm_for_prediction(prompt: str) -> dict:
    """基于 PI 研究方向预测其科研轨迹。"""
    if not settings.deepseek_api_key:
        return DEFAULT_FALLBACK

    try:
        gateway = AiGatewayService()
        messages = [
            {"role": "system", "content": "你是一个科研领域转移预测专家，只返回JSON格式结果。"},
            {"role": "user", "content": prompt},
        ]
        result = gateway.chat(messages=messages, temperature=0.3, max_tokens=2000)
        raw = result.get("reply", "")
        if not raw:
            return DEFAULT_FALLBACK
        return parse_prediction_response(raw)
    except Exception:  # noqa: BLE001  # AI gateway call / JSON parsing can fail
        logger.exception("LLM prediction call failed")
        return DEFAULT_FALLBACK


def parse_prediction_response(raw_response: str) -> dict:
    """解析 AI 返回的预测结果。"""
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        parsed = json.loads(cleaned)
        predicted = parsed.get("predicted_areas", [])
        if not isinstance(predicted, list):
            predicted = []
        for p in predicted:
            if not isinstance(p, dict):
                continue
            p.setdefault("probability", 0.0)
            p.setdefault("trend", "stable")
            p.setdefault("driver", "")
        return {
            "predicted_areas": predicted,
            "confidence": min(max(float(parsed.get("confidence", 0.0)), 0.0), 1.0),
            "rationale": str(parsed.get("rationale", "")),
            "transition_path": parsed.get("transition_path", []),
            "key_turning_points": parsed.get("key_turning_points", []),
        }
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return DEFAULT_FALLBACK
