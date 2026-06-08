"""link recruiter contacts to job applications

Revision ID: 0015_app_recruiters
Revises: 0014_archive_view
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015_app_recruiters"
down_revision: Union[str, None] = "0014_archive_view"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_recruiter_contacts",
        sa.Column("job_application_id", sa.Integer(), nullable=False),
        sa.Column("recruiter_contact_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recruiter_contact_id"], ["recruiter_contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_application_id", "recruiter_contact_id"),
    )


def downgrade() -> None:
    op.drop_table("application_recruiter_contacts")
