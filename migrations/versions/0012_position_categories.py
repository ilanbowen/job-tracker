"""add position categories

Revision ID: 0012_categories
Revises: 0011_status_views
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_categories"
down_revision: Union[str, None] = "0011_status_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_CATEGORIES = [
    ("Devops", 10),
    ("IT", 20),
]


def upgrade() -> None:
    op.create_table(
        "position_categories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_position_categories_name"),
    )
    op.create_index("ix_position_categories_id", "position_categories", ["id"], unique=False)
    op.create_index("ix_position_categories_name", "position_categories", ["name"], unique=True)

    op.add_column("job_applications", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_index("ix_job_applications_category_id", "job_applications", ["category_id"], unique=False)
    op.create_foreign_key(
        "fk_job_applications_category_id_position_categories",
        "job_applications",
        "position_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    categories_table = sa.table(
        "position_categories",
        sa.column("name", sa.String(length=80)),
        sa.column("display_order", sa.Integer()),
    )
    bind = op.get_bind()
    for name, display_order in DEFAULT_CATEGORIES:
        bind.execute(categories_table.insert().values(name=name, display_order=display_order))


def downgrade() -> None:
    op.drop_constraint("fk_job_applications_category_id_position_categories", "job_applications", type_="foreignkey")
    op.drop_index("ix_job_applications_category_id", table_name="job_applications")
    op.drop_column("job_applications", "category_id")
    op.drop_index("ix_position_categories_name", table_name="position_categories")
    op.drop_index("ix_position_categories_id", table_name="position_categories")
    op.drop_table("position_categories")
