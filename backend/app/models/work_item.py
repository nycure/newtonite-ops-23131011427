from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import WorkItemType, WorkItemPriority, WorkItemStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.team import Team
    from app.models.activity import ActivityEvent, Comment


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[WorkItemType] = mapped_column(String(30), nullable=False)
    priority: Mapped[WorkItemPriority] = mapped_column(String(20), default=WorkItemPriority.MEDIUM, nullable=False, index=True)
    status: Mapped[WorkItemStatus] = mapped_column(String(30), default=WorkItemStatus.OPEN, nullable=False, index=True)

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Compound Indexes for scale and fast dashboard queries
    __table_args__ = (
        Index("ix_work_items_team_status", "team_id", "status"),
        Index("ix_work_items_team_priority", "team_id", "priority"),
        Index("ix_work_items_team_created", "team_id", "created_at"),
        Index("ix_work_items_assignee_status", "assignee_id", "status"),
    )

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="work_items")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_items")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_id], back_populates="created_items")
    activity_events: Mapped[List["ActivityEvent"]] = relationship("ActivityEvent", back_populates="work_item", cascade="all, delete-orphan", order_by="ActivityEvent.created_at.desc()")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="work_item", cascade="all, delete-orphan", order_by="Comment.created_at.asc()")
