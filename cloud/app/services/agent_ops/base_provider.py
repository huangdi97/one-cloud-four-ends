"""Abstract base classes and factory for BioPulse AI providers."""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

from cloud.app.config.provider_config import ProviderConfig, ProviderMode, ProviderType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BaseLLM(abc.ABC):
    """Abstract base class for LLM providers.

    Implementations must provide:
    - generate(prompt, context) -> str
    """

    @abc.abstractmethod
    def generate(self, prompt: str, context: str | None = None) -> str: ...

    def close(self) -> None:
        pass


class BaseASR(abc.ABC):
    """Abstract base class for ASR (speech-to-text) providers.

    Implementations must provide:
    - transcribe(audio) -> str
    """

    @abc.abstractmethod
    def transcribe(self, audio: bytes) -> str: ...

    def close(self) -> None:
        pass


class BaseTTS(abc.ABC):
    """Abstract base class for TTS (text-to-speech) providers.

    Implementations must provide:
    - synthesize(text) -> bytes
    """

    @abc.abstractmethod
    def synthesize(self, text: str) -> bytes: ...

    def close(self) -> None:
        pass


class BasePush(abc.ABC):
    """Abstract base class for push notification providers.

    Implementations must provide:
    - send(recipient, message) -> bool
    """

    @abc.abstractmethod
    def send(self, recipient: str, message: str) -> bool: ...

    def close(self) -> None:
        pass


def get_provider(
    provider_type: ProviderType,
    config: ProviderConfig | None = None,
) -> BaseLLM | BaseASR | BaseTTS | BasePush:
    """Factory: return a provider instance based on config mode.

    Args:
        provider_type: Which type of provider to create (LLM, ASR, TTS, PUSH).
        config: Optional override; uses get_provider_config() if None.

    Returns:
        A concrete provider instance (Local or Api variant).
    """
    from cloud.app.services.agent_ops.api_providers import ApiASR, ApiLLM, ApiPush, ApiTTS
    from cloud.app.services.platform_svc.local_providers import LocalASR, LocalLLM, LocalPush, LocalTTS

    if config is None:
        from cloud.app.config.provider_config import get_provider_config

        config = get_provider_config()

    _PROVIDER_MAP: dict[ProviderType, tuple[type, type]] = {
        ProviderType.LLM: (LocalLLM, ApiLLM),
        ProviderType.ASR: (LocalASR, ApiASR),
        ProviderType.TTS: (LocalTTS, ApiTTS),
        ProviderType.PUSH: (LocalPush, ApiPush),
    }

    local_cls, api_cls = _PROVIDER_MAP[provider_type]

    settings = getattr(config, provider_type.value)

    if not settings.enabled:
        logger.warning("Provider %s is disabled, falling back to local", provider_type.value)
        return local_cls(settings)

    if settings.mode == ProviderMode.API:
        logger.info("Creating API provider for %s", provider_type.value)
        return api_cls(settings)

    logger.info("Creating local provider for %s", provider_type.value)
    return local_cls(settings)
