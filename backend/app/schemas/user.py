from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.models.enums import TeamRole


class TeamMembershipOut(BaseModel):
    team_id: int
    team_name: str
    role: TeamRole

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime
    memberships: List[TeamMembershipOut] = []

    class Config:
        from_attributes = True


class TeamOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
