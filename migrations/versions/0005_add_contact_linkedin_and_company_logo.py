"""add contact linkedin urls and company logo filename

Revision ID: 0005_contacts_logo
Revises: 0004_add_company_contacts
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_contacts_logo"
down_revision: Union[str, None] = "0004_add_company_contacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_applications", sa.Column("company_logo_filename", sa.String(length=255), nullable=True))
    op.add_column("job_applications", sa.Column("hr_contact_linkedin_url", sa.Text(), nullable=True))
    for idx in range(1, 5):
        op.add_column("job_applications", sa.Column(f"other_contact_{idx}_linkedin_url", sa.Text(), nullable=True))


def downgrade() -> None:
    for idx in range(4, 0, -1):
        op.drop_column("job_applications", f"other_contact_{idx}_linkedin_url")
    op.drop_column("job_applications", "hr_contact_linkedin_url")
    op.drop_column("job_applications", "company_logo_filename")
