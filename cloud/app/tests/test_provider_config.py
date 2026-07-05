"""Tests for the provider configuration and factory system."""

from __future__ import annotations

import logging
import os

import pytest

from cloud.app.config.provider_config import (
    ProviderConfig,
    ProviderMode,
    ProviderSettings,
    ProviderType,
    get_provider_config,
)
from cloud.app.services.agent_ops.api_providers import ApiASR, ApiLLM, ApiPush, ApiTTS
from cloud.app.services.agent_ops.base_provider import BaseASR, BaseLLM, BasePush, BaseTTS, get_provider
from cloud.app.services.platform_svc.local_providers import LocalASR, LocalLLM, LocalPush, LocalTTS


class TestProviderConfig:
    def test_provider_type_enum_values(self) -> None:
        assert ProviderType.LLM.value == "llm"
        assert ProviderType.ASR.value == "asr"
        assert ProviderType.TTS.value == "tts"
        assert ProviderType.PUSH.value == "push"

    def test_provider_mode_enum_values(self) -> None:
        assert ProviderMode.LOCAL.value == "local"
        assert ProviderMode.API.value == "api"

    def test_provider_settings_defaults(self) -> None:
        s = ProviderSettings(service="llm")
        assert s.enabled is True
        assert s.mode == ProviderMode.LOCAL
        assert s.timeout_seconds == 30
        assert s.max_retries == 3

    def test_provider_config_defaults(self) -> None:
        cfg = ProviderConfig()
        assert cfg.llm.service == "llm"
        assert cfg.asr.service == "asr"
        assert cfg.tts.service == "tts"
        assert cfg.push.service == "push"
        assert cfg.llm.mode == ProviderMode.LOCAL

    def test_get_provider_config_default_local(self) -> None:
        cfg = get_provider_config()
        assert cfg.llm.mode == ProviderMode.LOCAL
        assert cfg.asr.mode == ProviderMode.LOCAL
        assert cfg.tts.mode == ProviderMode.LOCAL
        assert cfg.push.mode == ProviderMode.LOCAL

    def test_get_provider_config_env_override(self) -> None:
        os.environ["PROVIDER_LLM_MODE"] = "api"
        os.environ["PROVIDER_ASR_MODE"] = "api"
        os.environ["PROVIDER_TTS_ENDPOINT"] = "https://tts.example.com"
        os.environ["PROVIDER_LLM_API_KEY"] = "sk-test-key"
        try:
            cfg = get_provider_config()
            assert cfg.llm.mode == ProviderMode.API
            assert cfg.asr.mode == ProviderMode.API
            assert cfg.tts.mode == ProviderMode.LOCAL
            assert cfg.tts.api_endpoint == "https://tts.example.com"
            assert cfg.llm.api_key == "sk-test-key"
        finally:
            os.environ.pop("PROVIDER_LLM_MODE", None)
            os.environ.pop("PROVIDER_ASR_MODE", None)
            os.environ.pop("PROVIDER_TTS_ENDPOINT", None)
            os.environ.pop("PROVIDER_LLM_API_KEY", None)


class TestAbstractBases:
    def test_base_llm_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseLLM()  # type: ignore

    def test_base_asr_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseASR()  # type: ignore

    def test_base_tts_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseTTS()  # type: ignore

    def test_base_push_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BasePush()  # type: ignore

    def test_base_close_is_noop(self) -> None:
        class MinimalLLM(BaseLLM):
            def generate(self, prompt: str, context: str | None = None) -> str:
                return ""

        instance = MinimalLLM()
        instance.close()


class TestFactory:
    def test_get_provider_llm_local(self) -> None:
        cfg = ProviderConfig()
        cfg.llm.mode = ProviderMode.LOCAL
        provider = get_provider(ProviderType.LLM, cfg)
        assert isinstance(provider, LocalLLM)

    def test_get_provider_llm_api(self) -> None:
        cfg = ProviderConfig()
        cfg.llm.mode = ProviderMode.API
        cfg.llm.api_endpoint = "https://api.openai.com/v1"
        cfg.llm.api_key = "sk-test"
        provider = get_provider(ProviderType.LLM, cfg)
        assert isinstance(provider, ApiLLM)

    def test_get_provider_asr_local(self) -> None:
        provider = get_provider(ProviderType.ASR)
        assert isinstance(provider, LocalASR)

    def test_get_provider_tts_local(self) -> None:
        provider = get_provider(ProviderType.TTS)
        assert isinstance(provider, LocalTTS)

    def test_get_provider_push_local(self) -> None:
        provider = get_provider(ProviderType.PUSH)
        assert isinstance(provider, LocalPush)


class TestLocalProviders:
    def test_local_llm_generate(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        settings = ProviderSettings(service="llm")
        provider = LocalLLM(settings)
        result = provider.generate("Hello")
        assert "[LocalLLM] mock response" in result
        assert "[LocalLLM]" in caplog.text

    def test_local_asr_transcribe(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        settings = ProviderSettings(service="asr")
        provider = LocalASR(settings)
        result = provider.transcribe(b"audio data")
        assert "[LocalASR] mock transcription" in result
        assert "[LocalASR]" in caplog.text

    def test_local_tts_synthesize(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        settings = ProviderSettings(service="tts")
        provider = LocalTTS(settings)
        result = provider.synthesize("Hello world")
        assert b"[LocalTTS mock audio]" in result
        assert "[LocalTTS]" in caplog.text

    def test_local_push_send(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        settings = ProviderSettings(service="push")
        provider = LocalPush(settings)
        result = provider.send("user@test.com", "Test message")
        assert result is True
        assert "[LocalPush]" in caplog.text


class TestApiProviders:
    def test_api_asr_fallback_to_local(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        settings = ProviderSettings(service="asr", mode=ProviderMode.API)
        provider = ApiASR(settings)
        result = provider.transcribe(b"audio data")
        assert "[LocalASR] mock transcription" in result
        assert "falling back to local" in caplog.text

    def test_api_tts_fallback_to_local(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        settings = ProviderSettings(service="tts", mode=ProviderMode.API)
        provider = ApiTTS(settings)
        result = provider.synthesize("Hello")
        assert b"[LocalTTS mock audio]" in result
        assert "falling back to local" in caplog.text

    def test_api_push_fallback_to_local(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        settings = ProviderSettings(service="push", mode=ProviderMode.API)
        provider = ApiPush(settings)
        result = provider.send("user@test.com", "msg")
        assert result is True
        assert "falling back to local" in caplog.text

    @pytest.mark.asyncio
    async def test_api_llm_fallback_on_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        settings = ProviderSettings(
            service="llm",
            mode=ProviderMode.API,
            api_endpoint="https://nonexistent.invalid",
            api_key="sk-test",
            timeout_seconds=1,
            max_retries=1,
        )
        provider = ApiLLM(settings)
        result = await provider.generate("Hello")
        assert "[LocalLLM] mock response" in result
        assert "falling back to local" in caplog.text
        provider.close()


class TestProviderSettingsCustomization:
    def test_custom_settings(self) -> None:
        s = ProviderSettings(
            service="llm",
            enabled=True,
            mode=ProviderMode.API,
            api_endpoint="https://custom.api/v1",
            api_key="sk-custom",
            model_name="gpt-4o-mini",
            timeout_seconds=60,
            max_retries=5,
        )
        assert s.service == "llm"
        assert s.enabled is True
        assert s.mode == ProviderMode.API
        assert s.api_endpoint == "https://custom.api/v1"
        assert s.api_key == "sk-custom"
        assert s.model_name == "gpt-4o-mini"
        assert s.timeout_seconds == 60
        assert s.max_retries == 5

    def test_disabled_provider_falls_back(self) -> None:
        cfg = ProviderConfig()
        cfg.llm.enabled = False
        cfg.llm.mode = ProviderMode.API
        provider = get_provider(ProviderType.LLM, cfg)
        assert isinstance(provider, LocalLLM)
