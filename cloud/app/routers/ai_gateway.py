"""AI 网关，提供 LLM 对话接口。"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from cloud.app.services.agent_ops.ai_gateway_service import AiGatewayService
from shared.auth_scope import require_scope
from shared.base import ApiResponse, success

router = APIRouter(prefix="/ai", tags=["AI Gateway"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)


class ChatResponse(BaseModel):
    reply: str
    usage: dict[str, Any]


@router.post("/chat", response_model=ApiResponse[ChatResponse], tags=["AI Gateway"])
def chat(
    request: Request,
    body: ChatRequest,
    _: dict = Depends(require_scope("visit")),
    service: AiGatewayService = Depends(),
) -> Any:
    result = service.chat(body.messages, body.temperature, body.max_tokens, current_user.get("id"))  # noqa: F821
    return success(ChatResponse(reply=result["reply"], usage=result["usage"]))
