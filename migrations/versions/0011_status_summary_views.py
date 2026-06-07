"""assign statuses to application summary views

Revision ID: 0011_status_views
Revises: 0010_statuses
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_status_views"
down_revision: Union[str, None] = "0010_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INTERVIEW_STATUSES = ["Phone Screen", "Technical Interview", "Final Interview", "Offer"]


def upgrade() -> None:
    op.add_column(
        "job_statuses",
        sa.Column("pipeline_stage", sa.String(length=30), nullable=False, server_default="intake"),
    )
    op.create_index("ix_job_statuses_pipeline_stage", "job_statuses", ["pipeline_stage"], unique=False)

    bind = op.get_bind()
    for status_name in INTERVIEW_STATUSES:
        bind.execute(
            sa.text("UPDATE job_statuses SET pipeline_stage = 'interview' WHERE name = :name"),
            {"name": status_name},
        )


def downgrade() -> None:
    op.drop_index("ix_job_statuses_pipeline_stage", table_name="job_statuses")
    op.drop_column("job_statuses", "pipeline_stage")
