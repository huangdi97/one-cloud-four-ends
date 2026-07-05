"""Local (stub) provider implementations for BioPulse AI services."""

from __future__ import annotations

import logging

from cloud.app.config.provider_config import ProviderSettings
from cloud.app.services.agent_ops.base_provider import BaseASR, BaseLLM, BasePush, BaseTTS

logger = logging.getLogger(__name__)


class LocalLLM(BaseLLM):
    """Local LLM provider stub — logs and returns a mock response."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings

    def generate(self, prompt: str, context: str | None = None) -> str:
        logger.info("[LocalLLM] generating… prompt=%s context=%s", prompt[:64], context[:64] if context else None)
        return f"[LocalLLM] mock response for: {prompt[:64]}"


class LocalASR(BaseASR):
    """Local ASR provider stub — logs and returns a mock transcription."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings

    def transcribe(self, audio: bytes) -> str:
        logger.info("[LocalASR] transcribing… audio_size=%d", len(audio))
        return "[LocalASR] mock transcription"


class LocalTTS(BaseTTS):
    """Local TTS provider stub — logs and returns empty bytes."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings

    def synthesize(self, text: str) -> bytes:
        logger.info("[LocalTTS] synthesizing… text=%s", text[:64])
        return b"[LocalTTS mock audio]"


class LocalPush(BasePush):
    """Local push provider stub — logs the notification."""

    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings

    def send(self, recipient: str, message: str) -> bool:
        logger.info("[LocalPush] sending to=%s message=%s", recipient, message[:64])
        return True
