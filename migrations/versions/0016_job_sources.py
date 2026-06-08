"""manage job application source values

Revision ID: 0016_job_sources
Revises: 0015_app_recruiters
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_job_sources"
down_revision: Union[str, None] = "0015_app_recruiters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_SOURCES = [
    (10, "LinkedIn"),
    (20, "Company Website"),
    (30, "External Recruiter"),
    (40, "Referral"),
    (50, "Other"),
]


def upgrade() -> None:
    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_job_sources_id"), "job_sources", ["id"], unique=False)
    op.create_index(op.f("ix_job_sources_name"), "job_sources", ["name"], unique=True)

    bind = op.get_bind()
    for display_order, name in DEFAULT_SOURCES:
        bind.execute(
            sa.text(
                """
                INSERT INTO job_sources (name, display_order)
                VALUES (:name, :display_order)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"name": name, "display_order": display_order},
        )

    existing_sources = bind.execute(
        sa.text(
            """
            SELECT DISTINCT source
            FROM job_applications
            WHERE source IS NOT NULL AND source <> ''
            ORDER BY source
            """
        )
    ).fetchall()
    next_order = 100
    for row in existing_sources:
        source_name = row[0]
        bind.execute(
            sa.text(
                """
                INSERT INTO job_sources (name, display_order)
                VALUES (:name, :display_order)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"name": source_name, "display_order": next_order},
        )
        next_order += 10


def downgrade() -> None:
    op.drop_index(op.f("ix_job_sources_name"), table_name="job_sources")
    op.drop_index(op.f("ix_job_sources_id"), table_name="job_sources")
    op.drop_table("job_sources")
