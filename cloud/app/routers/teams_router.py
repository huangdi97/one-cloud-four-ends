"""团队管理路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.team_service import TeamService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/teams", tags=["团队管理"])


class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class TeamMemberAdd(BaseModel):
    user_id: int
    role: str = "member"


@router.post("", status_code=status.HTTP_201_CREATED, tags=["团队管理"])
def create_team(
    body: TeamCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """Create a new team."""
    result = service.create_team(
        name=body.name,
        description=body.description,
        created_by=int(current_user["sub"]),
    )
    return success(data=result)


@router.get("", tags=["团队管理"])
def list_teams(
    name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """List teams with optional name filter and pagination."""
    result = service.list_teams(name=name, page=page, page_size=page_size)
    return success(data=result)


@router.get("/{team_id:int}", tags=["团队管理"])
def get_team(
    team_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """Get a single team with its members."""
    return success(data=service.get_team(team_id))


@router.patch("/{team_id:int}", tags=["团队管理"])
def update_team(
    team_id: int,
    body: TeamUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """Update team fields dynamically."""
    result = service.update_team(
        team_id,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
    )
    return success(data=result)


@router.delete("/{team_id:int}", tags=["团队管理"])
def delete_team(
    team_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """Soft-delete a team by setting is_active=0."""
    service.delete_team(team_id)
    return success()


@router.post("/{team_id:int}/members", status_code=status.HTTP_201_CREATED, tags=["团队管理"])
def add_team_member(
    team_id: int,
    body: TeamMemberAdd,
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """Add a member to a team."""
    service.add_member(team_id, body.user_id, body.role)
    return success()


@router.delete("/{team_id:int}/members/{user_id:int}", tags=["团队管理"])
def remove_team_member(
    team_id: int,
    user_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: TeamService = Depends(),
) -> Any:
    """Remove a member from a team."""
    service.remove_member(team_id, user_id)
    return success()
