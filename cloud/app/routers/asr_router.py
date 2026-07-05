from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from starlette import status

from cloud.app.services.platform_svc.asr_service import AsrService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/v1/asr", tags=["ASR录音摘要"])


class UploadResponse(BaseModel):
    task_id: str
    status: str = "pending"


class TranscriptResponse(BaseModel):
    task_id: str
    transcript: str
    status: str


class SummaryResponse(BaseModel):
    task_id: str
    summary: dict
    status: str


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=UploadResponse, summary="上传录音文件", tags=["ASR录音摘要"])
async def upload_audio(
    file: UploadFile = File(...),
    service: AsrService = Depends(),
    _: dict = Depends(require_scope("visit")),
):
    import os

    os.makedirs("uploads/audio", exist_ok=True)
    file_path = f"uploads/audio/{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    result = service.process_audio(file_path)
    return success(data=UploadResponse(**result))


@router.get("/{task_id}/transcript", summary="获取转写结果", tags=["ASR录音摘要"])
def get_transcript(task_id: str, service: AsrService = Depends()):
    result = service.get_transcript(task_id)
    if not result:
        from fastapi import HTTPException

        raise HTTPException(404, "task not found")
    return success(data=TranscriptResponse(**result))


@router.get("/{task_id}/summary", summary="获取结构化摘要", tags=["ASR录音摘要"])
def get_summary(task_id: str, service: AsrService = Depends()):
    result = service.get_summary(task_id)
    if not result:
        from fastapi import HTTPException

        raise HTTPException(404, "task not found")
    return success(data=SummaryResponse(**result))
