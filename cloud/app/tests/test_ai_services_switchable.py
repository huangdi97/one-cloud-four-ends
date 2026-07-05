"""Tests for AI service switchable behavior (ASR, TTS, LLM, Notification)."""

from __future__ import annotations

import logging
import os
import tempfile

import pytest

from cloud.app.config.provider_config import ProviderMode, ProviderSettings
from cloud.app.services.agent_ops.llm_service import LlmService
from cloud.app.services.platform_svc.asr_service import AsrService
from cloud.app.services.platform_svc.tts_service import TtsService
from cloud.app.services.rep_workbench.notification_service import NotificationService


class TestAsrService:
    def test_disabled_returns_error(self) -> None:
        settings = ProviderSettings(service="asr", enabled=False)
        svc = AsrService(provider_settings=settings)
        result = svc.transcribe("/nonexistent/file.wav")
        assert result == {"error": "ASR disabled", "text": ""}

    def test_local_mode_returns_mock(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake audio data")
            tmp = f.name
        try:
            settings = ProviderSettings(service="asr", mode=ProviderMode.LOCAL)
            svc = AsrService(provider_settings=settings)
            result = svc.transcribe(tmp)
            assert "text" in result
            assert result["confidence"] == 0.95
            assert "segments" in result
        finally:
            os.unlink(tmp)

    def test_api_mode_falls_back(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"audio")
            tmp = f.name
        try:
            settings = ProviderSettings(
                service="asr",
                mode=ProviderMode.API,
                api_endpoint="https://nonexistent.invalid",
                api_key="sk-test",
            )
            svc = AsrService(provider_settings=settings)
            result = svc.transcribe(tmp)
            assert "text" in result
        finally:
            os.unlink(tmp)

    def test_file_not_found_raises(self) -> None:
        settings = ProviderSettings(service="asr", mode=ProviderMode.LOCAL)
        svc = AsrService(provider_settings=settings)
        with pytest.raises(FileNotFoundError):
            svc.transcribe("/nonexistent/file.wav")

    def test_switch_mode(self) -> None:
        settings = ProviderSettings(service="asr", mode=ProviderMode.LOCAL)
        svc = AsrService(provider_settings=settings)
        assert svc.settings.mode == ProviderMode.LOCAL
        svc.switch_mode(ProviderMode.API)
        assert svc.settings.mode == ProviderMode.API

    def test_process_audio_and_get_transcript(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"test audio")
            tmp = f.name
        try:
            settings = ProviderSettings(service="asr", mode=ProviderMode.LOCAL)
            svc = AsrService(provider_settings=settings)
            proc = svc.process_audio(tmp)
            assert "task_id" in proc
            task_id = proc["task_id"]
            transcript = svc.get_transcript(task_id)
            assert transcript is not None
            assert transcript["task_id"] == task_id
            assert "transcript" in transcript
            summary = svc.get_summary(task_id)
            assert summary is not None
            assert "summary" in summary
        finally:
            os.unlink(tmp)


class TestTtsService:
    def test_disabled_returns_error(self) -> None:
        settings = ProviderSettings(service="tts", enabled=False)
        svc = TtsService(provider_settings=settings)
        result = svc.synthesize("hello")
        assert result["error"] == "TTS disabled"
        assert result["audio"] == b""

    def test_local_mode_returns_mock(self) -> None:
        settings = ProviderSettings(service="tts", mode=ProviderMode.LOCAL)
        svc = TtsService(provider_settings=settings)
        result = svc.synthesize("hello world")
        assert "audio" in result
        assert b"[LocalTTS mock audio]" in result["audio"]
        assert result["format"] == "wav"

    def test_api_mode_falls_back(self) -> None:
        settings = ProviderSettings(
            service="tts",
            mode=ProviderMode.API,
            api_endpoint="https://nonexistent.invalid",
            api_key="sk-test",
        )
        svc = TtsService(provider_settings=settings)
        result = svc.synthesize("hello")
        assert "audio" in result

    def test_switch_mode(self) -> None:
        settings = ProviderSettings(service="tts", mode=ProviderMode.LOCAL)
        svc = TtsService(provider_settings=settings)
        assert svc.settings.mode == ProviderMode.LOCAL
        svc.switch_mode(ProviderMode.API)
        assert svc.settings.mode == ProviderMode.API


class TestLlmService:
    @pytest.mark.asyncio
    async def test_disabled_returns_indicator(self) -> None:
        settings = ProviderSettings(service="llm", enabled=False)
        svc = LlmService(provider_settings=settings)
        result = await svc.generate("hello")
        assert result == "[LlmService] disabled"

    @pytest.mark.asyncio
    async def test_local_mode_returns_mock(self) -> None:
        settings = ProviderSettings(service="llm", mode=ProviderMode.LOCAL)
        svc = LlmService(provider_settings=settings)
        result = await svc.generate("hello")
        assert "[LocalLLM] mock response" in result

    @pytest.mark.asyncio
    async def test_api_fallback_to_local(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        settings = ProviderSettings(
            service="llm",
            mode=ProviderMode.API,
            api_endpoint="https://nonexistent.invalid",
            api_key="sk-test",
            timeout_seconds=1,
            max_retries=1,
        )
        svc = LlmService(provider_settings=settings, fallback_to_local=True)
        result = await svc.generate("hello")
        assert "[LocalLLM] mock response" in result
        assert "falling back to local" in caplog.text

    @pytest.mark.asyncio
    async def test_api_no_fallback_raises(self) -> None:
        settings = ProviderSettings(
            service="llm",
            mode=ProviderMode.API,
            api_endpoint="https://nonexistent.invalid",
            api_key="sk-test",
            timeout_seconds=1,
            max_retries=1,
        )
        svc = LlmService(provider_settings=settings, fallback_to_local=False)
        with pytest.raises(Exception):
            await svc.generate("hello")

    @pytest.mark.asyncio
    async def test_switch_mode(self) -> None:
        settings = ProviderSettings(service="llm", mode=ProviderMode.LOCAL)
        svc = LlmService(provider_settings=settings)
        assert svc.settings.mode == ProviderMode.LOCAL
        svc.switch_mode(ProviderMode.API)
        assert svc.settings.mode == ProviderMode.API

    @pytest.mark.asyncio
    async def test_generate_with_context(self) -> None:
        settings = ProviderSettings(service="llm", mode=ProviderMode.LOCAL)
        svc = LlmService(provider_settings=settings)
        result = await svc.generate("hello", context="be concise")
        assert "[LocalLLM] mock response" in result


class TestNotificationService:
    def test_disabled_push_logs_only(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        settings = ProviderSettings(service="push", enabled=False)
        svc = NotificationService(provider_settings=settings)
        svc._push_notification(title="Test", body="Body", user_id=1)
        assert "Push disabled" in caplog.text

    def test_local_push_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        settings = ProviderSettings(service="push", mode=ProviderMode.LOCAL)
        svc = NotificationService(provider_settings=settings)
        svc._push_notification(title="Hello", body="World", user_id=42)
        assert "[LocalPush]" in caplog.text

    def test_api_push_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        settings = ProviderSettings(
            service="push",
            mode=ProviderMode.API,
            api_endpoint="https://nonexistent.invalid",
            api_key="sk-test",
        )
        svc = NotificationService(provider_settings=settings)
        svc._push_notification(title="Hi", body="There", user_id=7)
        assert "falling back to local" in caplog.text


@pytest.mark.asyncio
async def test_audio_to_visit_draft_pipeline() -> None:
    from unittest.mock import patch

    from cloud.app.services.rep_workbench.visit_extraction_service import generate_visit_draft

    mock_transcript = "Patient reports headache and fever since three days"
    mock_confidence = 0.92
    mock_fields = {"visit_summary": "Headache and fever reported, no medication prescribed"}

    with (
        patch(
            "cloud.app.services.visit_extraction_service.transcribe_audio",
            return_value={"text": mock_transcript, "confidence": mock_confidence},
        ),
        patch(
            "cloud.app.services.visit_extraction_service.extract_visit_fields",
            return_value=mock_fields,
        ),
    ):
        result = await generate_visit_draft("/tmp/test_audio.wav", "user_001")

    assert result["user_id"] == "user_001"
    assert result["source_audio"] == "/tmp/test_audio.wav"
    assert result["transcript"] == mock_transcript
    assert result["asr_confidence"] == mock_confidence
    assert result["extracted_fields"] == mock_fields


@pytest.mark.asyncio
async def test_audio_to_visit_draft_asr_fails() -> None:
    from unittest.mock import patch

    from cloud.app.services.rep_workbench.visit_extraction_service import generate_visit_draft

    with patch(
        "cloud.app.services.visit_extraction_service.transcribe_audio",
        return_value={"text": "", "confidence": 0.0},
    ):
        result = await generate_visit_draft("/tmp/test_audio.wav", "user_001")

    assert result["user_id"] == "user_001"
    assert result["transcript"] == ""
    assert result["asr_confidence"] == 0.0
    assert result["extracted_fields"] is None


@pytest.mark.asyncio
async def test_audio_to_visit_draft_extraction_fails() -> None:
    from unittest.mock import patch

    from cloud.app.services.rep_workbench.visit_extraction_service import generate_visit_draft

    mock_transcript = "Patient reports headache and fever since three days"
    mock_confidence = 0.92

    with (
        patch(
            "cloud.app.services.visit_extraction_service.transcribe_audio",
            return_value={"text": mock_transcript, "confidence": mock_confidence},
        ),
        patch(
            "cloud.app.services.visit_extraction_service.extract_visit_fields",
            side_effect=Exception("LLM extraction failed"),
        ),
    ):
        with pytest.raises(Exception, match="LLM extraction failed"):
            await generate_visit_draft("/tmp/test_audio.wav", "user_001")
