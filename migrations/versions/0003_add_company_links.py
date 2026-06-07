"""add company website and linkedin page

Revision ID: 0003_add_company_links
Revises: 0002_remove_priority
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_company_links"
down_revision: Union[str, None] = "0002_remove_priority"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_applications", sa.Column("company_website", sa.Text(), nullable=True))
    op.add_column("job_applications", sa.Column("company_linkedin_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_applications", "company_linkedin_url")
    op.drop_column("job_applications", "company_website")
