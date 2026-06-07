"""add company address and city

Revision ID: 0008_company_location
Revises: 0007_recruiters
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_company_location"
down_revision: Union[str, None] = "0007_recruiters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("city", sa.String(length=120), nullable=True))
    op.create_index("ix_companies_city", "companies", ["city"])


def downgrade() -> None:
    op.drop_index("ix_companies_city", table_name="companies")
    op.drop_column("companies", "city")
    op.drop_column("companies", "address")
