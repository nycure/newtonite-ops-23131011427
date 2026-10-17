# Engineering Decisions & Architectural Trade-offs

This document details the core architectural and systems-level engineering decisions made during the design and implementation of **Newtonite Ops ("Operations Under Pressure")**.

In accordance with Newtonite's evaluation criteria, our focus was placed on **correctness under pressure, transactional integrity, concurrency guarantees, and defensible trade-offs** over surface-level feature bloat.

---

## 1. Concurrency Control: Atomic Conditional Update vs. Pessimistic Table Locking

### Context
In high-velocity operational environments, multiple team members frequently race to claim high-priority, unassigned work items (e.g., P0 database outage alerts). A naive `SELECT` followed by `UPDATE` suffers from race conditions where two engineers can simultaneously see the item as unassigned and both receive a success confirmation, leading to duplicate ownership or split-brain operational triage.

### Options Considered
1. **Pessimistic Table/Row Locking (`SELECT ... FOR UPDATE`):**
   * *Pros:* Blocks competing transactions until the lock is released.
   * *Cons:* Substantially degrades throughput under load; risks connection pool starvation and distributed deadlocks if long-running transactions hold row locks.
2. **Conditional Atomic Write (`UPDATE ... WHERE id = :id AND assignee_id IS NULL`):**
   * *Pros:* Leverages database engine row-level isolation natively. Exactly one transaction modifies the row; all competing transactions modify 0 rows and are immediately rejected without lock queues.
   * *Cons:* Requires checking the returned affected row count or `RETURNING` clause to detect collisions.

### Choice & Implementation
We chose **Conditional Atomic Updates**:
```sql
UPDATE work_items 
SET assignee_id = :user_id, version = version + 1, updated_at = NOW()
WHERE id = :item_id AND assignee_id IS NULL;
```
If `rowcount == 0`, the transaction rolls back and immediately issues an `HTTP 409 Conflict` with a human-readable explanation and the current owner. In the same transaction, an append-only `activity_events` audit record is committed.

### Trade-off
* **Trade-off:** Competing users receive an explicit collision rejection rather than waiting in an implicit queue. In operational triage, failing fast with an instant notification that a teammate claimed the incident is far superior to silent queuing.

---

## 2. Stale Edit Protection: Optimistic Locking with Versioning vs. Last-Write-Wins

### Context
When multiple engineers inspect the same complex incident or compliance ticket, one engineer may update the description or priority while another is composing changes. In a default "Last-Write-Wins" design, the second update silently overwrites the first engineer's changes without either party noticing.

### Options Considered
1. **Last-Write-Wins (Blind Overwrite):**
   * *Pros:* Easiest to implement.
   * *Cons:* Destructive data loss in collaborative team environments.
2. **Pessimistic Checkout Lock (Draft/Locking):**
   * *Pros:* Prevents opening the edit form simultaneously.
   * *Cons:* Prone to abandoned locks when an engineer closes their browser or gets called into a meeting.
3. **Optimistic Locking via Monotonic Version Counter:**
   * *Pros:* Non-blocking reads, zero lock overhead; guarantees that writes only succeed if the client's version matches the database version.
   * *Cons:* Requires client-side version tracking and reconciliation handling upon conflict.

### Choice & Implementation
We chose **Optimistic Locking via an integer `version` field**. Every modifying request (`PATCH /api/items/{id}`) must submit the expected version:
```sql
UPDATE work_items 
SET title = :title, description = :desc, version = version + 1, updated_at = NOW()
WHERE id = :item_id AND version = :client_version;
```
If a mismatch is detected, the server aborts the transaction and returns `HTTP 409 Conflict` containing the current database version and latest values, triggering the frontend conflict banner with a 1-click state refresh.

### Trade-off
* **Trade-off:** The client must re-read before resubmitting. This deliberate friction prevents silent data overwrites.

---

## 3. Request Deduplication: Database-Backed Idempotency Keys vs. Distributed Cache (Redis)

### Context
Network timeouts, flaky connections, or double-clicks on critical operations (e.g. creating an emergency payment issue or executing a state transition) can trigger retried requests that duplicate records or duplicate side effects.

### Options Considered
1. **Redis Cache with TTL for Request Signatures:**
   * *Pros:* Extremely fast key-value lookups with automatic TTL expiration.
   * *Cons:* Dual-system failure mode; if Redis is down or desynchronized from PostgreSQL, requests either fail open (allowing duplicates) or fail closed (crashing the API).
2. **PostgreSQL Relational `idempotency_keys` Table:**
   * *Pros:* Committed in the **exact same ACID transaction** as the business entity. Zero possibility of database commit with missing idempotency key.
   * *Cons:* Requires periodic table housekeeping/cleanup of expired keys.

### Choice & Implementation
We chose **Transactional Database Idempotency Keys**. Clients submit an `Idempotency-Key` header (UUID). The server checks `idempotency_keys`:
* If present and the SHA-256 hash of the request payload matches: immediately returns the cached HTTP response status and body without re-executing logic.
* If present with a modified payload: returns `HTTP 422 Unprocessable Entity` (tamper protection).
* If new: creates the record, stores the response, and commits in a single transaction.

### Trade-off
* **Trade-off:** Small write overhead on the primary database for mutations with idempotency headers in exchange for 100% ACID consistency.

---

## 4. Workflow State Machine & Resource-Level Authorization Architecture

### Context
A work item undergoes an operational lifecycle: `Open` $\rightarrow$ `In Progress` $\rightarrow$ `Awaiting Approval` $\rightarrow$ `Resolved` $\rightarrow$ `Closed`. An unauthorized jump (e.g., jumping from `Open` to `Closed`) or an unauthorized approval (e.g., a junior `Member` approving their own PR/fix) violates operational compliance.

### Options Considered
1. **Ad-hoc Validation in Route Handlers:**
   * *Pros:* Quick to hack together.
   * *Cons:* Scattered permissions, high risk of authorization bypass when new endpoints are added.
2. **Centralized Workflow Transition Matrix & Role Dependency Scoping:**
   * *Pros:* Single source of truth for all permitted state transitions and role checks. Easy to audit, unit test, and adapt.
   * *Cons:* Requires strict abstraction and explicit team membership querying.

### Choice & Implementation
We centralized the workflow in `workflow_service.py` with an immutable transition graph:
```python
ALLOWED_TRANSITIONS = {
    "open": {"in_progress"},
    "in_progress": {"awaiting_approval", "open"},
    "awaiting_approval": {"resolved", "in_progress"},
    "resolved": {"closed", "in_progress"},
    "closed": {"in_progress"},
}
ELEVATED_TRANSITIONS = {
    ("awaiting_approval", "resolved"), # Approval step restricted to Lead / Admin
    ("closed", "in_progress"),        # Reopening restricted to Lead / Admin
}
```
All read/write operations strictly verify that `user_id` possesses an active membership in the item's `team_id`. External users receive `403 Forbidden`.

### Trade-off
* **Trade-off:** Strict enforcement prevents informal "fast-tracking" of approvals, ensuring team compliance.

---

## 5. Reliable Async Work: Transactional Outbox Pattern vs. Direct Broker Publishing

### Context
State transitions and task assignments require downstream asynchronous notifications (e.g., notifying assignees, syncing audit logs). If an application attempts dual-writing to PostgreSQL and a message broker (RabbitMQ/Kafka/Email API), a crash between the database commit and the broker call results in lost notifications.

### Options Considered
1. **Direct Publishing inside Request Handler:**
   * *Pros:* Direct and simple.
   * *Cons:* "Dual-write" anti-pattern. If network drops after DB commit, message is permanently lost.
2. **Transactional Outbox Table with Asynchronous Polling Worker:**
   * *Pros:* Guaranteed At-Least-Once delivery. The event row (`outbox_jobs`) is written in the exact same database transaction as the work item change. A resilient worker picks it up with exponential backoff retries.
   * *Cons:* Introduces a small polling latency (1–2 seconds) and requires idempotent consumer handlers.

### Choice & Implementation
We implemented the **Transactional Outbox Pattern**:
1. During `create_work_item`, `claim_work_item`, and `transition_work_item`, an `OutboxJob` is staged in the SQLAlchemy session.
2. Both the work item update, the activity log, and the outbox job commit simultaneously.
3. An asynchronous worker continuously processes pending jobs, tracks attempts, applies exponential backoff ($2^\text{attempts}$ seconds), and marks failed jobs after exceeding `max_attempts`.

### Trade-off
* **Trade-off:** Asynchronous delivery over immediate synchronous confirmation, ensuring bulletproof system resiliency during network or third-party outages.

---

## 6. What Was Intentionally Not Built & Known Limitations

1. **Real-time WebSockets:** Replaced with fast refetching and client-side polling. WebSockets add substantial connection-state complexity without adding meaningful value for an operational triage workflow.
2. **SSO / Complex User Registration:** Replaced with pre-seeded users and role-switching toolbar to maximize reviewer evaluation speed.
3. **Partitioned Cold Storage:** For production scale $> 10\times$ (millions of items), the `activity_events` and `outbox_jobs` tables should be range-partitioned by `created_at` or offloaded to cold storage.
