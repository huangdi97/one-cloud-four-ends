"""LLMExtractionService — uses LLM to extract structured fields from ASR transcripts."""

from __future__ import annotations

import json
import logging
from typing import Any

from cloud.app.services.agent_ops.llm_service import LlmService
from cloud.app.services.brain.memory_service import MemoryService
from cloud.app.services.platform_svc.extraction_schema import ExtractionSchema

logger = logging.getLogger(__name__)


class LLMExtractionError(Exception):
    """Raised when LLM extraction fails."""


class SchemaValidationError(LLMExtractionError):
    """Raised when required fields are missing in the LLM response."""


class LLMExtractionService:
    def __init__(
        self,
        llm_service: LlmService,
        memory_service: MemoryService,
    ) -> None:
        self._llm = llm_service
        self._memory = memory_service

    async def extract_structured_fields(
        self,
        transcript: str,
        schema: ExtractionSchema,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(transcript, schema)
        raw = await self._llm.generate(prompt)
        result = self._parse_response(raw, schema)
        namespace = self._memory.get_namespace("visit_extraction")
        namespace.store(schema.field_name, json.dumps(result, ensure_ascii=False))
        return result

    def _build_prompt(self, transcript: str, schema: ExtractionSchema) -> str:
        type_hint = schema.type
        if schema.type == "enum" and schema.enum_options:
            type_hint = f"enum({', '.join(schema.enum_options)})"

        return (
            f"Extract the following field from the transcript.\n"
            f"Field name: {schema.field_name}\n"
            f"Description: {schema.description}\n"
            f"Type: {type_hint}\n"
            f"Transcript: {transcript}\n\n"
            f"Return ONLY a valid JSON object with key '{schema.field_name}'."
        )

    def _parse_response(self, raw: str, schema: ExtractionSchema) -> dict[str, Any]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            raise LLMExtractionError(f"LLM response is not valid JSON: {raw[:200]}")

        if schema.field_name not in parsed:
            raise SchemaValidationError(f"Required field '{schema.field_name}' missing in LLM response. Got keys: {list(parsed.keys())}")

        return parsed
