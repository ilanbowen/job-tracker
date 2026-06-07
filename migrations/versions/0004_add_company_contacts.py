"""add detailed company contacts

Revision ID: 0004_add_company_contacts
Revises: 0003_add_company_links
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_add_company_contacts"
down_revision: Union[str, None] = "0003_add_company_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_applications", sa.Column("hr_contact_phone", sa.String(length=80), nullable=True))
    for idx in range(1, 5):
        op.add_column("job_applications", sa.Column(f"other_contact_{idx}_name", sa.String(length=200), nullable=True))
        op.add_column("job_applications", sa.Column(f"other_contact_{idx}_position", sa.String(length=200), nullable=True))
        op.add_column("job_applications", sa.Column(f"other_contact_{idx}_phone", sa.String(length=80), nullable=True))


def downgrade() -> None:
    for idx in range(4, 0, -1):
        op.drop_column("job_applications", f"other_contact_{idx}_phone")
        op.drop_column("job_applications", f"other_contact_{idx}_position")
        op.drop_column("job_applications", f"other_contact_{idx}_name")
    op.drop_column("job_applications", "hr_contact_phone")
