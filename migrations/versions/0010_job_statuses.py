"""add job application statuses

Revision ID: 0010_statuses
Revises: 0009_recruiter_logo
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_statuses"
down_revision: Union[str, None] = "0009_recruiter_logo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_STATUSES = [
    "Interested",
    "Applied",
    "Recruiter Contacted",
    "Phone Screen",
    "Technical Interview",
    "Final Interview",
    "Offer",
    "Rejected",
    "Ghosted",
    "Closed",
]


def upgrade() -> None:
    op.create_table(
        "job_statuses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_job_statuses_name"),
    )
    op.create_index("ix_job_statuses_id", "job_statuses", ["id"], unique=False)
    op.create_index("ix_job_statuses_name", "job_statuses", ["name"], unique=True)

    bind = op.get_bind()
    existing_statuses = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT DISTINCT status FROM job_applications WHERE status IS NOT NULL AND status <> ''")
        ).fetchall()
    ]

    ordered_statuses: list[str] = []
    for status in DEFAULT_STATUSES + existing_statuses:
        if status and status not in ordered_statuses:
            ordered_statuses.append(status)

    statuses_table = sa.table(
        "job_statuses",
        sa.column("name", sa.String(length=80)),
        sa.column("display_order", sa.Integer()),
    )
    for index, status in enumerate(ordered_statuses, start=10):
        bind.execute(statuses_table.insert().values(name=status, display_order=index * 10))


def downgrade() -> None:
    op.drop_index("ix_job_statuses_name", table_name="job_statuses")
    op.drop_index("ix_job_statuses_id", table_name="job_statuses")
    op.drop_table("job_statuses")
