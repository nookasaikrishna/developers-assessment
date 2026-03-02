"""Add worklog payment tables (remittance, worklog, time_entry)

Revision ID: f8a2c1d9e047
Revises: 1a31ce608336
Create Date: 2026-03-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "f8a2c1d9e047"
down_revision = "1a31ce608336"
branch_labels = None
depends_on = None


def upgrade():
    # remittance must be created before worklog because worklog references it
    op.create_table(
        "remittance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remittance_user_id", "remittance", ["user_id"])
    op.create_index("ix_remittance_status", "remittance", ["status"])
    op.create_index("ix_remittance_created_at", "remittance", ["created_at"])

    op.create_table(
        "worklog",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "task_name",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("remittance_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["remittance_id"], ["remittance.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worklog_user_id", "worklog", ["user_id"])
    op.create_index("ix_worklog_status", "worklog", ["status"])
    op.create_index("ix_worklog_created_at", "worklog", ["created_at"])
    op.create_index("ix_worklog_remittance_id", "worklog", ["remittance_id"])

    op.create_table(
        "time_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("worklog_id", sa.UUID(), nullable=False),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=512),
            nullable=False,
        ),
        sa.Column("hours", sa.Float(), nullable=False),
        sa.Column("hourly_rate", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["worklog_id"], ["worklog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_entry_worklog_id", "time_entry", ["worklog_id"])
    op.create_index("ix_time_entry_recorded_at", "time_entry", ["recorded_at"])


def downgrade():
    op.drop_table("time_entry")
    op.drop_table("worklog")
    op.drop_table("remittance")
