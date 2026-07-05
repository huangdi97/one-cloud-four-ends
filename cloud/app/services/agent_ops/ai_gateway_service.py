"""AI 网关服务，统一封装对大语言模型（DeepSeek）的调用。"""

import json
import logging
import math
import urllib.error
import urllib.request

from fastapi import HTTPException
from starlette import status

from cloud.app.services.agent_ops.token_budget_service import TokenBudgetService
from shared.ai_gateway import TIMEOUT_SECONDS
from shared.base_service import BaseService
from shared.config import settings

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

_semantic_cache = None


class AiGatewayService(BaseService):
    """AI 网关服务，负责调用 DeepSeek API 并记录 Token 用量。"""

    def _get_api_key(self) -> str:
        """获取 DeepSeek API 密钥，若未配置则抛出 503 异常。

        返回:
            str: API 密钥字符串
        """
        key = settings.deepseek_api_key
        if not key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DEEPSEEK_API_KEY not configured",
            )
        return key

    def _extract_reply(self, payload: dict) -> str:
        """从 DeepSeek API 响应中提取回复文本。

        参数:
            payload: API 返回的 JSON 响应字典

        返回:
            提取出的回复字符串，无 choices 时返回空字符串
        """
        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "")

    def _select_model(self, messages: list[dict]) -> str:
        """根据消息长度与复杂度选择模型。

        参数:
            messages: 对话消息列表

        返回:
            模型名称字符串
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        complex_keywords = ["分析", "评估", "推理", "比较", "生成报告"]
        has_complex_keyword = any(keyword in " ".join(m.get("content", "") for m in messages) for keyword in complex_keywords)
        if total_chars < 200 and not has_complex_keyword:
            return "deepseek-chat"
        return "deepseek-chat"

    def chat(self, messages: list[dict], temperature: float, max_tokens: int, user_id: int, model_override: str | None = None) -> dict:
        """调用 DeepSeek API 进行对话，包含语义缓存与 Token 用量记录。

        参数:
            messages: 对话消息列表
            temperature: 生成温度
            max_tokens: 最大生成 token 数
            user_id: 用户 ID，用于记录用量
            model_override: 可选，强制指定模型

        返回:
            包含 reply 和 usage 的字典
        """
        global _semantic_cache
        if _semantic_cache is None:
            from cloud.app.services.platform_svc.semantic_cache_service import SemanticCache

            _semantic_cache = SemanticCache()

        last_msg = messages[-1] if messages else {}
        if last_msg.get("role") == "user" and len(last_msg.get("content", "")) < 500:
            cached = _semantic_cache.get(last_msg["content"])
            if cached is not None:
                return cached

        api_key = self._get_api_key()

        model = model_override if model_override else self._select_model(messages)

        req_body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req_data = json.dumps(req_body).encode("utf-8")

        req = urllib.request.Request(
            DEEPSEEK_URL,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read()
        except urllib.error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"DeepSeek API call failed: {exc}",
            )

        payload = json.loads(raw)
        reply = self._extract_reply(payload)
        usage = payload.get("usage", {})

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost = prompt_tokens * 0.14 / 1e6 + completion_tokens * 0.28 / 1e6
        TokenBudgetService().record_usage(user_id, model, usage.get("total_tokens", 0), cost)

        result = {"reply": reply, "usage": usage}

        if last_msg.get("role") == "user" and len(last_msg.get("content", "")) < 500:
            _semantic_cache.set(last_msg["content"], result)

        return result


EMBEDDING_DIM = 128


def get_embedding(text: str) -> list[float] | None:
    """计算文本的 trigram 哈希嵌入向量（L2 归一化）。

    参数:
        text: 输入文本

    返回:
        归一化后的嵌入向量列表，失败时返回 None
    """
    try:
        vec = [0.0] * EMBEDDING_DIM
        for i in range(len(text) - 2):
            trigram = text[i : i + 3]
            h = hash(trigram) % EMBEDDING_DIM
            vec[h] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec
    except Exception:  # noqa: BLE001  # trigram hash / math operations have multiple failure modes
        logger.exception("get_embedding failed")
        return None
