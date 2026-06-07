"""add recruiter company logo filename

Revision ID: 0009_recruiter_logo
Revises: 0008_company_location
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_recruiter_logo"
down_revision: Union[str, None] = "0008_company_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recruiter_companies", sa.Column("logo_filename", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("recruiter_companies", "logo_filename")
