"""录音上传与草稿管理路由。"""

import os
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.visit_extraction_service import (
    confirm_draft,
    delete_draft,
    generate_visit_draft,
    get_user_drafts,
    save_draft,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/cloud/visit", tags=["拜访"])

_AES_KEY: bytes | None = None


def _get_aes_key() -> bytes:
    global _AES_KEY
    if _AES_KEY is not None:
        return _AES_KEY
    raw = os.getenv("RECORDING_ENCRYPTION_KEY", "")
    if raw:
        _AES_KEY = bytes.fromhex(raw) if len(raw) == 64 else raw.encode()[:32].ljust(32, b"\0")
    else:
        _AES_KEY = os.urandom(32)
    if len(_AES_KEY) != 32:
        _AES_KEY = _AES_KEY[:32].ljust(32, b"\0")
    return _AES_KEY


def encrypt_audio(data: bytes) -> tuple[bytes, bytes]:
    aesgcm = AESGCM(_get_aes_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce, ciphertext


@router.post("/upload-recording", status_code=status.HTTP_201_CREATED)
async def upload_recording(
    audio_file: UploadFile = File(...),
    user_id: str = Form(...),
    _: dict = Depends(require_scope("visit")),
):
    os.makedirs("uploads/audio", exist_ok=True)
    file_ext = os.path.splitext(audio_file.filename or "recording.wav")[1] or ".wav"
    timestamp = uuid.uuid4().hex[:8]
    file_name = f"rec_{timestamp}_{uuid.uuid4().hex}{file_ext}"
    file_path = f"uploads/audio/{file_name}"
    content = await audio_file.read()

    nonce, ciphertext = encrypt_audio(content)
    with open(file_path, "wb") as f:
        f.write(ciphertext)

    draft_data = await generate_visit_draft(file_path, user_id)
    draft_data["encrypted_key"] = nonce.hex()
    saved = save_draft(draft_data)

    return success(
        data={
            "draft_id": saved["id"],
            "transcript": draft_data["transcript"],
            "extracted_fields": draft_data["extracted_fields"],
            "status": saved.get("status", "draft"),
        }
    )


@router.get("/drafts")
def list_drafts(
    user_id: str,
    _: dict = Depends(require_scope("visit")),
):
    drafts = get_user_drafts(user_id)
    return success(data=drafts)


class ConfirmDraftBody(BaseModel):
    user_id: str
    edited_fields: dict


@router.post("/drafts/{draft_id}/confirm")
def confirm_draft_endpoint(
    draft_id: str,
    body: ConfirmDraftBody,
    _: dict = Depends(require_scope("visit")),
):
    result = confirm_draft(draft_id, body.user_id, body.edited_fields)
    if not result:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Draft not found")
    return success(data=result)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft_endpoint(
    draft_id: str,
    user_id: str,
    _: dict = Depends(require_scope("visit")),
):
    delete_draft(draft_id, user_id)
