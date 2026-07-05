"""
Visit extraction service.
Orchestrates ASR transcription and LLM-based structured field extraction
from voice-of-customer visit recordings.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta

from cloud.app.database import DB_PATH
from cloud.app.services.platform_svc.asr_service import transcribe_audio

DEFAULT_CONFIDENCE_THRESHOLD = 0.8

CREATE_DRAFTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS visit_drafts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    audio_file_path TEXT,
    encrypted_key TEXT,
    expires_at TEXT,
    transcript TEXT,
    extracted_fields TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    confirmed_by TEXT
)
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_drafts_table() -> None:
    conn = _get_conn()
    try:
        conn.execute(CREATE_DRAFTS_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def save_draft(draft_data: dict) -> dict:
    draft_id = draft_data.get("id", f"draft_{uuid.uuid4().hex}")
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_at = (datetime.utcnow() + timedelta(days=365 * 2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO visit_drafts (id, user_id, audio_file_path, encrypted_key, expires_at, transcript, extracted_fields, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                draft_id,
                draft_data["user_id"],
                draft_data.get("audio_file_path"),
                draft_data.get("encrypted_key"),
                expires_at,
                draft_data.get("transcript"),
                json.dumps(draft_data["extracted_fields"]) if draft_data.get("extracted_fields") else None,
                draft_data.get("status", "draft"),
                now,
            ),
        )
        conn.commit()
        return {**draft_data, "id": draft_id, "created_at": now, "expires_at": expires_at}
    finally:
        conn.close()


def get_user_drafts(user_id: str, status: str = None) -> list[dict]:
    conn = _get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM visit_drafts WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM visit_drafts WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def confirm_draft(draft_id: str, user_id: str, edited_fields: dict) -> dict:
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE visit_drafts SET status = 'confirmed', confirmed_at = ?, confirmed_by = ?, extracted_fields = ? WHERE id = ? AND user_id = ?",
            (now, user_id, json.dumps(edited_fields), draft_id, user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM visit_drafts WHERE id = ?", (draft_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


async def extract_visit_fields(transcript: str, confidence: float) -> dict:
    from cloud.app.services.agent_ops.llm_extraction_service import LLMExtractionService
    from cloud.app.services.agent_ops.llm_service import LlmService
    from cloud.app.services.brain.memory_service import MemoryService
    from cloud.app.services.platform_svc.extraction_schema import ExtractionSchema

    llm = LlmService()
    mem = MemoryService()
    svc = LLMExtractionService(llm, mem)
    schema = ExtractionSchema(
        field_name="visit_summary",
        description="Structured summary of the doctor visit including key discussion points, action items, and compliance markers",
        type="string",
    )
    return await svc.extract_structured_fields(transcript, schema)


def delete_draft(draft_id: str, user_id: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM visit_drafts WHERE id = ? AND user_id = ?",
            (draft_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


async def generate_visit_draft(audio_file: str, user_id: str) -> dict:
    asr_result = await transcribe_audio(audio_file)
    transcript = asr_result["text"]
    confidence = asr_result["confidence"]

    extracted = None
    if confidence > DEFAULT_CONFIDENCE_THRESHOLD:
        extracted = await extract_visit_fields(transcript, confidence)

    return {
        "user_id": user_id,
        "source_audio": audio_file,
        "transcript": transcript,
        "asr_confidence": confidence,
        "extracted_fields": extracted,
    }
