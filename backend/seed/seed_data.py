import asyncio
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import AsyncSessionLocal, init_db, engine
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.models.work_item import WorkItem
from app.models.activity import ActivityEvent, Comment
from app.models.enums import (
    TeamRole,
    WorkItemType,
    WorkItemPriority,
    WorkItemStatus,
    ActivityEventType,
)
from app.services.auth_service import get_password_hash

fake = Faker()
Faker.seed(42)
random.seed(42)


async def seed_database(num_items: int = 2500):
    print("Initializing schema for seeding...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        chk = await session.execute(select(User).limit(1))
        if chk.scalar_one_or_none():
            print("Database already has records. Cleaning up old data for clean seed...")
            await session.execute(delete(Comment))
            await session.execute(delete(ActivityEvent))
            await session.execute(delete(WorkItem))
            await session.execute(delete(TeamMembership))
            await session.execute(delete(Team))
            await session.execute(delete(User))
            await session.commit()

        print("Creating Teams...")
        teams_data = [
            ("Platform Engineering", "Core infrastructure, reliability, microservices, and DevOps"),
            ("Payments & Risk", "Payment processor integrations, fraud detection, billing workflows"),
            ("Customer Operations", "User escalations, customer support issues, onboarding triage"),
            ("Compliance & Legal", "Data protection regulations, regulatory auditing, KYC checks"),
        ]
        teams = []
        for name, desc in teams_data:
            t = Team(name=name, description=desc)
            session.add(t)
            teams.append(t)
        await session.flush()

        print("Creating Users...")
        default_pwd = get_password_hash("password123")
        users_def = [
            ("Alice Morgan", "alice@newtonite.io", default_pwd),
            ("Bob Chen", "bob@newtonite.io", default_pwd),
            ("Charlie Davis", "charlie@newtonite.io", default_pwd),
            ("Diana Prince", "diana@newtonite.io", default_pwd),
            ("Evan Wright", "evan@newtonite.io", default_pwd),
            ("Fiona Gallagher", "fiona@newtonite.io", default_pwd),
            ("George Clark", "george@newtonite.io", default_pwd),
            ("Hannah Abbott", "hannah@newtonite.io", default_pwd),
            ("Ian Malcolm", "ian@newtonite.io", default_pwd),
            ("Julia Roberts", "julia@newtonite.io", default_pwd),
            ("Outsider Owen", "owen@external.io", default_pwd),
        ]

        users = []
        for name, email, pwd in users_def:
            u = User(name=name, email=email, hashed_password=pwd)
            session.add(u)
            users.append(u)
        await session.flush()

        print("Assigning Team Memberships & Roles...")
        # Team 0: Platform Engineering
        session.add(TeamMembership(user_id=users[0].id, team_id=teams[0].id, role=TeamRole.LEAD))    # Alice: Lead
        session.add(TeamMembership(user_id=users[1].id, team_id=teams[0].id, role=TeamRole.MEMBER))  # Bob: Member
        session.add(TeamMembership(user_id=users[2].id, team_id=teams[0].id, role=TeamRole.VIEWER))  # Charlie: Viewer
        session.add(TeamMembership(user_id=users[3].id, team_id=teams[0].id, role=TeamRole.ADMIN))   # Diana: Admin

        # Team 1: Payments & Risk
        session.add(TeamMembership(user_id=users[0].id, team_id=teams[1].id, role=TeamRole.MEMBER))  # Alice: Member
        session.add(TeamMembership(user_id=users[4].id, team_id=teams[1].id, role=TeamRole.LEAD))    # Evan: Lead
        session.add(TeamMembership(user_id=users[5].id, team_id=teams[1].id, role=TeamRole.MEMBER))  # Fiona: Member
        session.add(TeamMembership(user_id=users[3].id, team_id=teams[1].id, role=TeamRole.ADMIN))   # Diana: Admin

        # Team 2: Customer Operations
        session.add(TeamMembership(user_id=users[1].id, team_id=teams[2].id, role=TeamRole.LEAD))    # Bob: Lead
        session.add(TeamMembership(user_id=users[6].id, team_id=teams[2].id, role=TeamRole.MEMBER))  # George: Member
        session.add(TeamMembership(user_id=users[7].id, team_id=teams[2].id, role=TeamRole.VIEWER))  # Hannah: Viewer
        session.add(TeamMembership(user_id=users[3].id, team_id=teams[2].id, role=TeamRole.ADMIN))   # Diana: Admin

        # Team 3: Compliance & Legal
        session.add(TeamMembership(user_id=users[8].id, team_id=teams[3].id, role=TeamRole.LEAD))    # Ian: Lead
        session.add(TeamMembership(user_id=users[9].id, team_id=teams[3].id, role=TeamRole.MEMBER))  # Julia: Member
        session.add(TeamMembership(user_id=users[3].id, team_id=teams[3].id, role=TeamRole.ADMIN))   # Diana: Admin
        # Owen has NO memberships (outsider)
        await session.flush()

        print("Seeding Key Benchmark & Demo Work Items...")
        # 1. Benchmark Urgent Unassigned for Concurrent Claim Testing
        demo_claim = WorkItem(
            title="CRITICAL: Database connection pool saturation under spike traffic",
            description="High priority alert triggered by APM. Connections reaching max limit on replica node 2. Unassigned and needs immediate triage.",
            type=WorkItemType.INCIDENT,
            priority=WorkItemPriority.URGENT,
            status=WorkItemStatus.OPEN,
            team_id=teams[0].id,
            assignee_id=None,
            created_by_id=users[3].id,
            due_date=datetime.utcnow() + timedelta(hours=4),
            version=1,
        )
        session.add(demo_claim)

        # 2. Benchmark Awaiting Approval for Lead Role Verification
        demo_approval = WorkItem(
            title="PROD-CHANGE: Rollout zero-downtime ledger migration for Q4 settlement",
            description="All automated verification tests passed. Waiting for team Lead sign-off before executing production schema migration.",
            type=WorkItemType.TASK,
            priority=WorkItemPriority.HIGH,
            status=WorkItemStatus.AWAITING_APPROVAL,
            team_id=teams[0].id,
            assignee_id=users[1].id,  # Bob
            created_by_id=users[1].id,
            due_date=datetime.utcnow() + timedelta(days=1),
            version=1,
        )
        session.add(demo_approval)

        # 3. Item Assigned to Alice
        demo_alice = WorkItem(
            title="Investigate cache invalidation latency in user session service",
            description="Redis cluster cluster-bus socket write timeouts reported during evening rollout.",
            type=WorkItemType.INCIDENT,
            priority=WorkItemPriority.HIGH,
            status=WorkItemStatus.IN_PROGRESS,
            team_id=teams[0].id,
            assignee_id=users[0].id,  # Alice
            created_by_id=users[3].id,
            due_date=datetime.utcnow() + timedelta(days=2),
            version=2,
        )
        session.add(demo_alice)
        await session.flush()

        # Seed activity logs and comments for demo items
        session.add(ActivityEvent(
            work_item_id=demo_claim.id,
            user_id=users[3].id,
            event_type=ActivityEventType.CREATED,
            message="Item created by Diana (Admin)",
        ))
        session.add(ActivityEvent(
            work_item_id=demo_approval.id,
            user_id=users[1].id,
            event_type=ActivityEventType.CREATED,
            message="Created work item",
        ))
        session.add(ActivityEvent(
            work_item_id=demo_approval.id,
            user_id=users[1].id,
            event_type=ActivityEventType.STATUS_CHANGED,
            from_value="in_progress",
            to_value="awaiting_approval",
            message="Requested Lead approval for production rollout",
        ))
        session.add(Comment(
            work_item_id=demo_approval.id,
            user_id=users[1].id,
            content="Checklist verified on staging environment. @Alice ready for review.",
        ))

        print(f"Generating {num_items} realistic work items for scale & cursor pagination...")
        types = list(WorkItemType)
        priorities = list(WorkItemPriority)
        statuses = list(WorkItemStatus)

        # Batch insert for fast seeding
        bulk_items = []
        for i in range(1, num_items + 1):
            team = random.choice(teams)
            creator = random.choice(users[:10])
            # 60% chance assigned, 40% unassigned
            assignee = random.choice(users[:10]) if random.random() > 0.4 else None
            status_val = random.choice(statuses)
            priority_val = random.choice(priorities)
            item_type = random.choice(types)

            title_templates = [
                f"Fix {item_type.value} in {team.name} batch pipeline #{i}",
                f"Investigate high latency in {team.name} endpoint #{i}",
                f"Resolve customer escalation #{1000 + i} for {team.name}",
                f"Quarterly compliance audit check #{i} for {team.name}",
                f"Patch memory leak in service worker instance #{i}",
                f"Retry failed payment transaction batch #{5000 + i}",
                f"Rebalance database partitions for {team.name} index #{i}",
            ]

            created_time = datetime.utcnow() - timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))

            item = WorkItem(
                title=random.choice(title_templates),
                description=fake.paragraph(nb_sentences=3),
                type=item_type,
                priority=priority_val,
                status=status_val,
                team_id=team.id,
                assignee_id=assignee.id if assignee else None,
                created_by_id=creator.id,
                due_date=created_time + timedelta(days=random.randint(1, 14)),
                version=1,
                created_at=created_time,
                updated_at=created_time,
            )
            bulk_items.append(item)

            if len(bulk_items) >= 500:
                session.add_all(bulk_items)
                await session.flush()
                bulk_items = []

        if bulk_items:
            session.add_all(bulk_items)
            await session.flush()

        await session.commit()
        print(f"Successfully seeded database with 4 teams, 11 users, and {num_items + 3} work items!")


if __name__ == "__main__":
    asyncio.run(seed_database(2500))
