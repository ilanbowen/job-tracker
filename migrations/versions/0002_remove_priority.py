"""remove priority from job applications

Revision ID: 0002_remove_priority
Revises: 0001_initial_schema
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_remove_priority"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_job_applications_priority"), table_name="job_applications")
    op.drop_column("job_applications", "priority")


def downgrade() -> None:
    op.add_column(
        "job_applications",
        sa.Column("priority", sa.String(length=30), nullable=False, server_default="Medium"),
    )
    op.create_index(op.f("ix_job_applications_priority"), "job_applications", ["priority"], unique=False)
    op.alter_column("job_applications", "priority", server_default=None)
