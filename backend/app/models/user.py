from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.team import TeamMembership
    from app.models.work_item import WorkItem
    from app.models.activity import ActivityEvent, Comment


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    memberships: Mapped[List["TeamMembership"]] = relationship("TeamMembership", back_populates="user", cascade="all, delete-orphan")
    assigned_items: Mapped[List["WorkItem"]] = relationship("WorkItem", foreign_keys="[WorkItem.assignee_id]", back_populates="assignee")
    created_items: Mapped[List["WorkItem"]] = relationship("WorkItem", foreign_keys="[WorkItem.created_by_id]", back_populates="creator")
    activity_events: Mapped[List["ActivityEvent"]] = relationship("ActivityEvent", back_populates="user")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="user")
