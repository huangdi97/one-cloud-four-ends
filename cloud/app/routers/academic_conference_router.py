"""Academic conference APIs."""

from fastapi import APIRouter, Depends
from starlette import status

from cloud.app.schemas.academic_conference import (
    ConferenceCheckinRequest,
    ConferenceInviteRequest,
    Meeting,
    MeetingCreate,
)
from cloud.app.services.intel.academic_conference_service import (
    checkin_meeting,
    create_meeting,
    get_analytics,
    invite_meeting,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/conference", tags=["线上学术会议"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Meeting, tags=["线上学术会议"])
def conference_create(body: MeetingCreate, _: dict = Depends(require_scope("visit"))):
    return success(data=create_meeting(body))


@router.post("/{conference_id}/invite", response_model=Meeting, tags=["线上学术会议"])
def conference_invite(
    conference_id: str,
    body: ConferenceInviteRequest | None = None,
    _: dict = Depends(require_scope("visit")),
):
    return success(data=invite_meeting(conference_id, body or ConferenceInviteRequest()))


@router.post("/{conference_id}/checkin", response_model=Meeting, tags=["线上学术会议"])
def conference_checkin(
    conference_id: str,
    body: ConferenceCheckinRequest | None = None,
    _: dict = Depends(require_scope("visit")),
):
    return success(data=checkin_meeting(conference_id, body or ConferenceCheckinRequest()))


@router.get("/{conference_id}/analytics", tags=["线上学术会议"])
def conference_analytics(conference_id: str, _: dict = Depends(require_scope("visit"))):
    return success(data=get_analytics(conference_id))
