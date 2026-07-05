"""LLM (Large Language Model) service — provider-switchable with fallback."""

from __future__ import annotations

import logging

from cloud.app.config.provider_config import ProviderMode, ProviderSettings
from cloud.app.services.agent_ops.base_provider import BaseLLM
from cloud.app.services.platform_svc.local_providers import LocalLLM

logger = logging.getLogger(__name__)


class _NoFallbackApiLLM(BaseLLM):
    """ApiLLM wrapper that never falls back — raises on failure."""

    def __init__(self, settings: ProviderSettings) -> None:
        from cloud.app.services.agent_ops.api_providers import ApiLLM

        self._inner = ApiLLM(settings)

    async def generate(self, prompt: str, context: str | None = None) -> str:
        result = await self._inner.generate(prompt, context)
        if "[LocalLLM]" in result or "mock response" in result:
            raise RuntimeError("API LLM failed and fallback is disabled")
        return result

    def close(self) -> None:
        self._inner.close()


class LlmService:
    """LLM service that delegates to LocalLLM or ApiLLM based on settings.

    When ``fallback_to_local`` is True (default), an API failure triggers an
    automatic fallback to the local (mock) provider.
    """

    def __init__(
        self,
        provider_settings: ProviderSettings | None = None,
        fallback_to_local: bool = True,
    ) -> None:
        self._settings = provider_settings or ProviderSettings(service="llm")
        self._fallback_to_local = fallback_to_local
        self._provider: BaseLLM | None = None

    @property
    def settings(self) -> ProviderSettings:
        return self._settings

    def _get_provider(self) -> BaseLLM:
        if not self._settings.enabled:
            return LocalLLM(self._settings)
        if self._settings.mode == ProviderMode.API:
            from cloud.app.services.agent_ops.api_providers import ApiLLM

            if self._fallback_to_local:
                return ApiLLM(self._settings)
            return _NoFallbackApiLLM(self._settings)
        return LocalLLM(self._settings)

    def switch_mode(self, mode: ProviderMode) -> None:
        self._settings.mode = mode
        self._provider = None

    async def generate(self, prompt: str, context: str | None = None) -> str:
        if not self._settings.enabled:
            return "[LlmService] disabled"
        logger.info("LLM generate: prompt=%s (mode=%s)", prompt[:64], self._settings.mode)
        provider = self._get_provider()
        if isinstance(provider, LocalLLM):
            return provider.generate(prompt, context)
        return await provider.generate(prompt, context)
