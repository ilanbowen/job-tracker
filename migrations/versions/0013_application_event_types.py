"""add managed application event types

Revision ID: 0013_event_types
Revises: 0012_categories
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_event_types"
down_revision: Union[str, None] = "0012_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_EVENT_TYPES = [
    ("Note", 10),
    ("Applied", 20),
    ("Follow-up", 30),
    ("Interview", 40),
    ("Status Change", 50),
    ("Rejected", 60),
    ("Offer", 70),
]


def upgrade() -> None:
    op.create_table(
        "application_event_types",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_application_event_types_name"),
    )
    op.create_index("ix_application_event_types_id", "application_event_types", ["id"], unique=False)
    op.create_index("ix_application_event_types_name", "application_event_types", ["name"], unique=True)

    bind = op.get_bind()
    event_types_table = sa.table(
        "application_event_types",
        sa.column("name", sa.String(length=100)),
        sa.column("display_order", sa.Integer()),
    )

    inserted: set[str] = set()
    for name, display_order in DEFAULT_EVENT_TYPES:
        bind.execute(event_types_table.insert().values(name=name, display_order=display_order))
        inserted.add(name.lower())

    existing_event_types = bind.execute(sa.text("SELECT DISTINCT event_type FROM application_events WHERE event_type IS NOT NULL AND event_type <> ''")).scalars().all()
    next_order = 100
    for name in existing_event_types:
        clean_name = str(name).strip()
        if not clean_name or clean_name.lower() in inserted:
            continue
        bind.execute(event_types_table.insert().values(name=clean_name, display_order=next_order))
        inserted.add(clean_name.lower())
        next_order += 10


def downgrade() -> None:
    op.drop_index("ix_application_event_types_name", table_name="application_event_types")
    op.drop_index("ix_application_event_types_id", table_name="application_event_types")
    op.drop_table("application_event_types")
