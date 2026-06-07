"""add recruiter companies and contacts

Revision ID: 0007_recruiters
Revises: 0006_normalize_contacts
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_recruiters"
down_revision: Union[str, None] = "0006_normalize_contacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recruiter_companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_recruiter_companies_name"),
    )
    op.create_index(op.f("ix_recruiter_companies_id"), "recruiter_companies", ["id"], unique=False)
    op.create_index(op.f("ix_recruiter_companies_name"), "recruiter_companies", ["name"], unique=False)

    op.create_table(
        "recruiter_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recruiter_company_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=250), nullable=True),
        sa.Column("phone", sa.String(length=80), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("date_added", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("date_contact_made", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["recruiter_company_id"], ["recruiter_companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recruiter_company_id",
            "name",
            "email",
            "phone",
            name="uq_recruiter_contacts_company_name_email_phone",
        ),
    )
    op.create_index(op.f("ix_recruiter_contacts_id"), "recruiter_contacts", ["id"], unique=False)
    op.create_index(op.f("ix_recruiter_contacts_name"), "recruiter_contacts", ["name"], unique=False)
    op.create_index(
        op.f("ix_recruiter_contacts_recruiter_company_id"),
        "recruiter_contacts",
        ["recruiter_company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_recruiter_contacts_recruiter_company_id"), table_name="recruiter_contacts")
    op.drop_index(op.f("ix_recruiter_contacts_name"), table_name="recruiter_contacts")
    op.drop_index(op.f("ix_recruiter_contacts_id"), table_name="recruiter_contacts")
    op.drop_table("recruiter_contacts")
    op.drop_index(op.f("ix_recruiter_companies_name"), table_name="recruiter_companies")
    op.drop_index(op.f("ix_recruiter_companies_id"), table_name="recruiter_companies")
    op.drop_table("recruiter_companies")
