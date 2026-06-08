"""add archive application summary view defaults

Revision ID: 0014_archive_view
Revises: 0013_event_types
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_archive_view"
down_revision: Union[str, None] = "0013_event_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ARCHIVE_STATUSES = ["Rejected", "Ghosted", "Closed"]


def upgrade() -> None:
    bind = op.get_bind()
    for status_name in ARCHIVE_STATUSES:
        bind.execute(
            sa.text("UPDATE job_statuses SET pipeline_stage = 'archive' WHERE name = :name"),
            {"name": status_name},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for status_name in ARCHIVE_STATUSES:
        bind.execute(
            sa.text("UPDATE job_statuses SET pipeline_stage = 'intake' WHERE name = :name"),
            {"name": status_name},
        )
