"""normalize companies and contacts

Revision ID: 0006_normalize_contacts
Revises: 0005_contacts_logo
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "0006_normalize_contacts"
down_revision: Union[str, None] = "0005_contacts_logo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("logo_filename", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_companies_name"),
    )
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=250), nullable=True),
        sa.Column("phone", sa.String(length=80), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("contact_type", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", "position", "phone", name="uq_contacts_company_name_position_phone"),
    )
    op.create_index(op.f("ix_contacts_id"), "contacts", ["id"], unique=False)
    op.create_index(op.f("ix_contacts_company_id"), "contacts", ["company_id"], unique=False)
    op.create_index(op.f("ix_contacts_name"), "contacts", ["name"], unique=False)

    op.create_table(
        "application_contacts",
        sa.Column("job_application_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_application_id", "contact_id"),
    )

    op.add_column("job_applications", sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_job_applications_company_id_companies",
        "job_applications",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_job_applications_company_id"), "job_applications", ["company_id"], unique=False)

    _migrate_existing_company_and_contact_data()


def _migrate_existing_company_and_contact_data() -> None:
    bind = op.get_bind()
    applications = bind.execute(
        text(
            """
            SELECT
              id,
              company_name,
              company_website,
              company_linkedin_url,
              company_logo_filename,
              contact_name,
              contact_email,
              hr_contact_phone,
              hr_contact_linkedin_url,
              other_contact_1_name,
              other_contact_1_position,
              other_contact_1_phone,
              other_contact_1_linkedin_url,
              other_contact_2_name,
              other_contact_2_position,
              other_contact_2_phone,
              other_contact_2_linkedin_url,
              other_contact_3_name,
              other_contact_3_position,
              other_contact_3_phone,
              other_contact_3_linkedin_url,
              other_contact_4_name,
              other_contact_4_position,
              other_contact_4_phone,
              other_contact_4_linkedin_url
            FROM job_applications
            ORDER BY id
            """
        )
    ).mappings().all()

    for app in applications:
        company_name = (app["company_name"] or "Unknown company").strip() or "Unknown company"
        company_id = bind.execute(
            text(
                """
                INSERT INTO companies (name, website, linkedin_url, logo_filename, created_at, updated_at)
                VALUES (:name, :website, :linkedin_url, :logo_filename, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (name) DO UPDATE SET
                  website = COALESCE(companies.website, EXCLUDED.website),
                  linkedin_url = COALESCE(companies.linkedin_url, EXCLUDED.linkedin_url),
                  logo_filename = COALESCE(companies.logo_filename, EXCLUDED.logo_filename),
                  updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """
            ),
            {
                "name": company_name,
                "website": app["company_website"],
                "linkedin_url": app["company_linkedin_url"],
                "logo_filename": app["company_logo_filename"],
            },
        ).scalar_one()

        bind.execute(
            text("UPDATE job_applications SET company_id = :company_id WHERE id = :application_id"),
            {"company_id": company_id, "application_id": app["id"]},
        )

        if any([app["contact_name"], app["contact_email"], app["hr_contact_phone"], app["hr_contact_linkedin_url"]]):
            _insert_contact_and_link(
                bind,
                application_id=app["id"],
                company_id=company_id,
                name=app["contact_name"] or "HR contact",
                position="HR",
                email=app["contact_email"],
                phone=app["hr_contact_phone"],
                linkedin_url=app["hr_contact_linkedin_url"],
                contact_type="HR",
            )

        for idx in range(1, 5):
            name = app[f"other_contact_{idx}_name"]
            position = app[f"other_contact_{idx}_position"]
            phone = app[f"other_contact_{idx}_phone"]
            linkedin_url = app[f"other_contact_{idx}_linkedin_url"]
            if any([name, position, phone, linkedin_url]):
                _insert_contact_and_link(
                    bind,
                    application_id=app["id"],
                    company_id=company_id,
                    name=name or f"Contact {idx}",
                    position=position,
                    email=None,
                    phone=phone,
                    linkedin_url=linkedin_url,
                    contact_type="Other",
                )


def _insert_contact_and_link(
    bind,
    *,
    application_id: int,
    company_id: int,
    name: str,
    position: str | None,
    email: str | None,
    phone: str | None,
    linkedin_url: str | None,
    contact_type: str | None,
) -> None:
    contact_id = bind.execute(
        text(
            """
            INSERT INTO contacts
              (company_id, name, position, email, phone, linkedin_url, contact_type, created_at, updated_at)
            VALUES
              (:company_id, :name, :position, :email, :phone, :linkedin_url, :contact_type, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """
        ),
        {
            "company_id": company_id,
            "name": name.strip() if name else "Contact",
            "position": position,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "contact_type": contact_type,
        },
    ).scalar_one()

    bind.execute(
        text(
            """
            INSERT INTO application_contacts (job_application_id, contact_id, role)
            VALUES (:application_id, :contact_id, :role)
            ON CONFLICT DO NOTHING
            """
        ),
        {"application_id": application_id, "contact_id": contact_id, "role": contact_type},
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_job_applications_company_id"), table_name="job_applications")
    op.drop_constraint("fk_job_applications_company_id_companies", "job_applications", type_="foreignkey")
    op.drop_column("job_applications", "company_id")

    op.drop_table("application_contacts")

    op.drop_index(op.f("ix_contacts_name"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_company_id"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_id"), table_name="contacts")
    op.drop_table("contacts")

    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_id"), table_name="companies")
    op.drop_table("companies")
