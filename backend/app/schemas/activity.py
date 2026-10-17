from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.enums import ActivityEventType


class ActivityEventOut(BaseModel):
    id: int
    work_item_id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    event_type: ActivityEventType
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    work_item_id: int
    user_id: int
    user_name: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
