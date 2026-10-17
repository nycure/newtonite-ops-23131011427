from enum import Enum


class TeamRole(str, Enum):
    VIEWER = "Viewer"
    MEMBER = "Member"
    LEAD = "Lead"
    ADMIN = "Admin"


class WorkItemType(str, Enum):
    INCIDENT = "incident"
    CUSTOMER_ISSUE = "customer_issue"
    PAYMENT = "payment"
    COMPLIANCE = "compliance"
    TASK = "task"


class WorkItemPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class WorkItemStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ActivityEventType(str, Enum):
    CREATED = "created"
    CLAIMED = "claimed"
    UNASSIGNED = "unassigned"
    ASSIGNED = "assigned"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    COMMENT_ADDED = "comment_added"
    UPDATED = "updated"


class OutboxJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
