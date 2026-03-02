import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import TimeEntry, User, UserCreate, WorkLog

logger = logging.getLogger(__name__)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    _seed_worklog_data(session)


def _seed_worklog_data(session: Session) -> None:
    """Seed freelancers, worklogs and time entries if none exist yet."""
    existing = session.exec(select(WorkLog)).first()
    if existing:
        return

    logger.info("Seeding sample worklog data...")

    # Create freelancer accounts
    freelancers_spec = [
        ("alice@freelance.dev", "Alice Johnson"),
        ("bob@freelance.dev", "Bob Martinez"),
        ("carol@freelance.dev", "Carol White"),
    ]
    freelancers = []
    for email, name in freelancers_spec:
        fl = session.exec(select(User).where(User.email == email)).first()
        if not fl:
            fl = crud.create_user(
                session=session,
                user_create=UserCreate(
                    email=email, password="Freelancer123!", full_name=name
                ),
            )
        freelancers.append(fl)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # (task_name, freelancer_index, days_ago, [(desc, hours, rate), ...])
    worklog_specs = [
        (
            "Homepage Redesign",
            0,
            25,
            [
                ("Initial wireframes", 3.0, 85.0),
                ("Figma mockups", 5.0, 85.0),
                ("CSS implementation", 4.5, 85.0),
            ],
        ),
        (
            "API Integration",
            0,
            20,
            [
                ("Endpoint mapping", 2.0, 85.0),
                ("Auth flow implementation", 6.0, 85.0),
                ("Error handling", 2.5, 85.0),
            ],
        ),
        (
            "Mobile App Navigation",
            1,
            22,
            [
                ("Navigation component", 4.0, 90.0),
                ("Tab bar implementation", 3.0, 90.0),
                ("Deep link handling", 2.5, 90.0),
            ],
        ),
        (
            "Push Notifications",
            1,
            15,
            [
                ("FCM setup", 2.0, 90.0),
                ("Notification templates", 3.5, 90.0),
            ],
        ),
        (
            "Database Schema Migration",
            2,
            28,
            [
                ("Schema analysis", 1.5, 95.0),
                ("Migration scripts", 4.0, 95.0),
                ("Rollback testing", 2.0, 95.0),
                ("Documentation", 1.0, 95.0),
            ],
        ),
        (
            "CI/CD Pipeline Setup",
            2,
            10,
            [
                ("Docker configuration", 3.0, 95.0),
                ("GitHub Actions workflow", 4.5, 95.0),
                ("Staging deployment", 2.0, 95.0),
            ],
        ),
        (
            "Payment Gateway Integration",
            0,
            5,
            [
                ("Stripe SDK setup", 2.0, 85.0),
                ("Checkout flow", 5.0, 85.0),
                ("Webhook handling", 3.0, 85.0),
            ],
        ),
        (
            "Analytics Dashboard",
            1,
            8,
            [
                ("Chart components", 6.0, 90.0),
                ("Data aggregation", 4.0, 90.0),
            ],
        ),
    ]

    for task_name, fl_idx, days_ago, entries in worklog_specs:
        fl = freelancers[fl_idx]
        wl_date = now - timedelta(days=days_ago)
        wl = WorkLog(task_name=task_name, user_id=fl.id, created_at=wl_date)
        session.add(wl)
        session.commit()
        session.refresh(wl)

        for desc, hrs, rate in entries:
            te = TimeEntry(
                worklog_id=wl.id,
                description=desc,
                hours=hrs,
                hourly_rate=rate,
                recorded_at=wl_date + timedelta(hours=1),
            )
            session.add(te)

        session.commit()

    logger.info("Seed data created successfully")
