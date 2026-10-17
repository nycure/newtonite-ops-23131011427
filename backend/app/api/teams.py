from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.schemas.user import TeamOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/teams", tags=["Teams"])


@router.get("", response_model=List[TeamOut])
async def list_teams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists teams that the current user belongs to."""
    user_team_ids = [m.team_id for m in current_user.memberships]
    if not user_team_ids:
        return []

    stmt = select(Team).where(Team.id.in_(user_team_ids)).order_by(Team.name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{team_id}/members")
async def list_team_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists members belonging to a team."""
    stmt = (
        select(TeamMembership)
        .options(selectinload(TeamMembership.user))
        .where(TeamMembership.team_id == team_id)
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    return [
        {
            "id": m.user.id,
            "name": m.user.name,
            "email": m.user.email,
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
        }
        for m in memberships
    ]
