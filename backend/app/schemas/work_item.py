from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.enums import WorkItemType, WorkItemPriority, WorkItemStatus
from app.schemas.activity import ActivityEventOut, CommentOut


class WorkItemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    type: WorkItemType
    priority: WorkItemPriority = WorkItemPriority.MEDIUM
    team_id: int
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None


class WorkItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    priority: Optional[WorkItemPriority] = None
    due_date: Optional[datetime] = None
    version: int = Field(..., description="Current version of the item required for optimistic locking")


class WorkItemTransitionRequest(BaseModel):
    target_status: WorkItemStatus
    comment: Optional[str] = None


class WorkItemAssignRequest(BaseModel):
    assignee_id: Optional[int] = None
    comment: Optional[str] = None
    version: int


class WorkItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: WorkItemType
    priority: WorkItemPriority
    status: WorkItemStatus
    team_id: int
    team_name: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    created_by_id: int
    creator_name: Optional[str] = None
    due_date: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkItemDetailOut(WorkItemOut):
    activity_events: List[ActivityEventOut] = []
    comments: List[CommentOut] = []


class WorkItemListResponse(BaseModel):
    items: List[WorkItemOut]
    total_count: int
    next_cursor: Optional[int] = None
    has_more: bool = False
