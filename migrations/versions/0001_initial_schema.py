"""initial schema

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("position_title", sa.String(length=250), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("remote_policy", sa.String(length=80), nullable=True),
        sa.Column("job_url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("date_applied", sa.Date(), nullable=True),
        sa.Column("next_action_date", sa.Date(), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=250), nullable=True),
        sa.Column("salary_range", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_applications_id"), "job_applications", ["id"], unique=False)
    op.create_index(op.f("ix_job_applications_company_name"), "job_applications", ["company_name"], unique=False)
    op.create_index(op.f("ix_job_applications_position_title"), "job_applications", ["position_title"], unique=False)
    op.create_index(op.f("ix_job_applications_status"), "job_applications", ["status"], unique=False)
    op.create_index(op.f("ix_job_applications_priority"), "job_applications", ["priority"], unique=False)

    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_application_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_events_id"), "application_events", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_application_events_id"), table_name="application_events")
    op.drop_table("application_events")
    op.drop_index(op.f("ix_job_applications_priority"), table_name="job_applications")
    op.drop_index(op.f("ix_job_applications_status"), table_name="job_applications")
    op.drop_index(op.f("ix_job_applications_position_title"), table_name="job_applications")
    op.drop_index(op.f("ix_job_applications_company_name"), table_name="job_applications")
    op.drop_index(op.f("ix_job_applications_id"), table_name="job_applications")
    op.drop_table("job_applications")
