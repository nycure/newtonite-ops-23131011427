from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.team import TeamMembership
from app.schemas.auth import Token, LoginRequest
from app.schemas.user import UserOut, TeamMembershipOut
from app.services.auth_service import verify_password, create_access_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login_json(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Logs in using JSON credentials and returns a JWT access token."""
    stmt = (
        select(User)
        .options(selectinload(User.memberships).selectinload(TeamMembership.team))
        .where(User.email == request.email)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": str(user.id), "email": user.email, "name": user.name})
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        name=user.name,
        email=user.email,
    )


@router.post("/token", response_model=Token)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 password form login endpoint for Swagger UI testing."""
    return await login_json(LoginRequest(email=form_data.username, password=form_data.password), db)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user with all team roles."""
    memberships = [
        TeamMembershipOut(
            team_id=m.team_id,
            team_name=m.team.name if m.team else f"Team {m.team_id}",
            role=m.role,
        )
        for m in current_user.memberships
    ]
    return UserOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        created_at=current_user.created_at,
        memberships=memberships,
    )


@router.get("/demo-users")
async def get_demo_users(db: AsyncSession = Depends(get_db)):
    """Returns seeded demo users for quick role switching in the reviewer dashboard."""
    stmt = (
        select(User)
        .options(selectinload(User.memberships).selectinload(TeamMembership.team))
        .order_by(User.id)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "roles": [
                {"team": m.team.name if m.team else f"Team {m.team_id}", "role": m.role.value}
                for m in u.memberships
            ],
        }
        for u in users
    ]
