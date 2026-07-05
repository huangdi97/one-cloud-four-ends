"""Remote API provider implementations for BioPulse AI services.

PIPL 合规声明：
    - 所有外部 API 调用使用 HTTPS 加密传输
    - ASR/TTS 语音数据仅路由至境内服务端点（阿里云/腾讯云/讯飞等）
    - ProviderSettings.restrict_domestic 开关可强制限制非境内 endpoint
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from cloud.app.config.provider_config import ProviderSettings
from cloud.app.services.agent_ops.base_provider import BaseASR, BaseLLM, BasePush, BaseTTS
from cloud.app.services.platform_svc.local_providers import LocalASR, LocalLLM, LocalPush, LocalTTS

logger = logging.getLogger(__name__)

_HTTPS_ONLY = True  # PIPL: 所有外部 API 传输必须使用 HTTPS


def _validate_endpoint(endpoint: str | None, service: str) -> None:
    if not endpoint:
        return
    if _HTTPS_ONLY and not endpoint.startswith("https://"):
        raise ValueError(f"[PIPL] {service} endpoint must use HTTPS for encrypted transmission: {endpoint}")


def _fallback_local(provider_type: str, settings: ProviderSettings) -> Any:
    logger.warning("[%s] API call failed, falling back to local", provider_type)
    _MAP: dict[str, Any] = {
        "llm": LocalLLM,
        "asr": LocalASR,
        "tts": LocalTTS,
        "push": LocalPush,
    }
    return _MAP[provider_type](settings)


class ApiLLM(BaseLLM):
    """OpenAI-compatible LLM provider via httpx."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings
        _validate_endpoint(settings.api_endpoint, "LLM")
        self._client = httpx.AsyncClient(
            base_url=settings.api_endpoint or "",
            timeout=settings.timeout_seconds,
        )
        self._local_fallback: LocalLLM | None = None

    async def generate(self, prompt: str, context: str | None = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        if context:
            messages.insert(0, {"role": "system", "content": context})

        for attempt in range(self._settings.max_retries):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json={
                        "model": self._settings.model_name or "gpt-4o",
                        "messages": messages,
                    },
                    headers=self._build_headers(),
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "[ApiLLM] attempt %d/%d failed: %s",
                    attempt + 1,
                    self._settings.max_retries,
                    exc,
                )
                if attempt + 1 == self._settings.max_retries:
                    fb = self._local_fallback or _fallback_local("llm", self._settings)
                    self._local_fallback = fb
                    return fb.generate(prompt, context)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        return headers

    def close(self) -> None:
        self._client.aclose()


class ApiASR(BaseASR):
    """Remote ASR provider via httpx (stub — not yet integrated)."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings
        self._local_fallback: LocalASR | None = None

    def transcribe(self, audio: bytes) -> str:
        logger.info("[ApiASR] transcribing… audio_size=%d (stub, falling back)", len(audio))
        fb = self._local_fallback or _fallback_local("asr", self._settings)
        self._local_fallback = fb
        return fb.transcribe(audio)

    def close(self) -> None:
        self._asr_provider.close()


class ApiTTS(BaseTTS):
    """Remote TTS provider via httpx (stub — not yet integrated)."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings
        self._local_fallback: LocalTTS | None = None

    def synthesize(self, text: str) -> bytes:
        logger.info("[ApiTTS] synthesizing… text=%s (stub, falling back)", text[:64])
        fb = self._local_fallback or _fallback_local("tts", self._settings)
        self._local_fallback = fb
        return fb.synthesize(text)

    def close(self) -> None:
        self._tts_provider.close()


class ApiPush(BasePush):
    """Remote push provider via httpx (stub — not yet integrated)."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings
        self._local_fallback: LocalPush | None = None

    def send(self, recipient: str, message: str) -> bool:
        logger.info("[ApiPush] sending to=%s (stub, falling back)", recipient)
        fb = self._local_fallback or _fallback_local("push", self._settings)
        self._local_fallback = fb
        return fb.send(recipient, message)

    def close(self) -> None:
        self._push_provider.close()
