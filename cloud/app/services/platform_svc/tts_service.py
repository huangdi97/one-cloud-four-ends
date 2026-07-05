"""TTS (Text-To-Speech) service — provider-switchable."""

from __future__ import annotations

import logging

from cloud.app.config.provider_config import ProviderMode, ProviderSettings
from cloud.app.services.agent_ops.api_providers import ApiTTS
from cloud.app.services.agent_ops.base_provider import BaseTTS
from cloud.app.services.platform_svc.local_providers import LocalTTS

logger = logging.getLogger(__name__)


class TtsService:
    """TTS service that delegates to LocalTTS or ApiTTS based on settings."""

    def __init__(self, provider_settings: ProviderSettings | None = None) -> None:
        self._settings = provider_settings or ProviderSettings(service="tts")
        self._provider: BaseTTS | None = None

    @property
    def settings(self) -> ProviderSettings:
        return self._settings

    def _get_provider(self) -> BaseTTS:
        if not self._settings.enabled:
            return LocalTTS(self._settings)
        if self._settings.mode == ProviderMode.API:
            return ApiTTS(self._settings)
        return LocalTTS(self._settings)

    def switch_mode(self, mode: ProviderMode) -> None:
        self._settings.mode = mode
        self._provider = None

    def synthesize(self, text: str) -> dict:
        if not self._settings.enabled:
            return {"error": "TTS disabled", "audio": b""}
        logger.info("TTS synthesize: text=%s (mode=%s)", text[:64], self._settings.mode)
        provider = self._get_provider()
        audio = provider.synthesize(text)
        return {"audio": audio, "format": "wav"}
