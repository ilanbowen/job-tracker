from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApplicationContact(Base):
    __tablename__ = "application_contacts"

    job_application_id: Mapped[int] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), primary_key=True
    )
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True, unique=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    applications: Mapped[list["JobApplication"]] = relationship(back_populates="company")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", order_by="Contact.name")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("company_id", "name", "position", "phone", name="uq_contacts_company_name_position_phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(250), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped[Company | None] = relationship(back_populates="contacts")
    applications: Mapped[list["JobApplication"]] = relationship(
        secondary="application_contacts", back_populates="contacts"
    )


class RecruiterCompany(Base):
    __tablename__ = "recruiter_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True, unique=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    contacts: Mapped[list["RecruiterContact"]] = relationship(back_populates="recruiter_company", order_by="RecruiterContact.name")


class RecruiterContact(Base):
    __tablename__ = "recruiter_contacts"
    __table_args__ = (
        UniqueConstraint("recruiter_company_id", "name", "email", "phone", name="uq_recruiter_contacts_company_name_email_phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recruiter_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("recruiter_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(250), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_added: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    date_contact_made: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    recruiter_company: Mapped[RecruiterCompany | None] = relationship(back_populates="contacts")


class JobStatus(Base):
    __tablename__ = "job_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pipeline_stage: Mapped[str] = mapped_column(String(30), nullable=False, default="intake", server_default="intake", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)

    # Legacy denormalized fields kept temporarily for migration/backward compatibility.
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    company_website: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    position_title: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remote_policy: Mapped[str | None] = mapped_column(String(80), nullable=True)
    job_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, default="Interested", index=True)
    date_applied: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Legacy contact fields kept temporarily for migration/backward compatibility.
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(250), nullable=True)
    hr_contact_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hr_contact_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_contact_1_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_1_position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_1_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    other_contact_1_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_contact_2_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_2_position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_2_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    other_contact_2_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_contact_3_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_3_position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_3_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    other_contact_3_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_contact_4_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_4_position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    other_contact_4_phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    other_contact_4_linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    salary_range: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped[Company | None] = relationship(back_populates="applications")
    contacts: Mapped[list[Contact]] = relationship(
        secondary="application_contacts", back_populates="applications", order_by="Contact.name"
    )
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="desc(ApplicationEvent.event_date)"
    )

    @property
    def display_company_name(self) -> str:
        return self.company.name if self.company else self.company_name

    @property
    def display_company_website(self) -> str | None:
        return self.company.website if self.company else self.company_website

    @property
    def display_company_linkedin_url(self) -> str | None:
        return self.company.linkedin_url if self.company else self.company_linkedin_url

    @property
    def display_company_logo_filename(self) -> str | None:
        return self.company.logo_filename if self.company else self.company_logo_filename

    @property
    def display_location(self) -> str | None:
        if self.company and self.company.city:
            return self.company.city
        return self.location


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="Note")
    event_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application: Mapped[JobApplication] = relationship(back_populates="events")
