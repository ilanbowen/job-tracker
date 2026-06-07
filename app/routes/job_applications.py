from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    ApplicationContact,
    ApplicationEvent,
    Company,
    Contact,
    JobApplication,
    JobStatus,
    RecruiterCompany,
    RecruiterContact,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _date_short(value: date | None) -> str:
    if not value:
        return "-"
    return value.strftime("%d/%m/%y")


def _date_month_day(value: date | None) -> str:
    if not value:
        return "-"
    return f"{value.strftime('%B')} {value.day}"


def _datetime_short(value: datetime | None) -> str:
    if not value:
        return "-"
    return value.strftime("%d/%m/%y %H:%M")


templates.env.filters["date_short"] = _date_short
templates.env.filters["date_month_day"] = _date_month_day
templates.env.filters["datetime_short"] = _datetime_short

DEFAULT_STATUS_OPTIONS = [
    "Interested",
    "Applied",
    "Recruiter Contacted",
    "Phone Screen",
    "Technical Interview",
    "Final Interview",
    "Offer",
    "Rejected",
    "Ghosted",
    "Closed",
]
INTERVIEW_STATUS_DEFAULTS = {"Phone Screen", "Technical Interview", "Final Interview", "Offer"}
PIPELINE_STAGE_OPTIONS = [
    ("intake", "Application Intake"),
    ("interview", "Interview Pipeline"),
]
PIPELINE_STAGE_LABELS = dict(PIPELINE_STAGE_OPTIONS)
PIPELINE_STAGE_DESCRIPTIONS = {
    "intake": "Track high-volume early applications before they become active interview processes.",
    "interview": "Track applications that have progressed into phone screens, interviews, offers, or other active responses.",
}

REMOTE_POLICY_OPTIONS = ["Remote", "Hybrid", "On-site", "Unknown"]
EVENT_TYPE_OPTIONS = ["Note", "Applied", "Follow-up", "Interview", "Status Change", "Rejected", "Offer"]
LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _logo_upload_dir() -> Path:
    logo_dir = Path(settings.logo_dir)
    logo_dir.mkdir(parents=True, exist_ok=True)
    return logo_dir


def _safe_logo_extension(filename: str | None) -> str | None:
    if not filename:
        return None
    suffix = Path(filename).suffix.lower()
    if suffix not in LOGO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported logo file type")
    return suffix


def _save_logo_upload(upload: UploadFile | None, prefix: str) -> str | None:
    if not upload or not upload.filename:
        return None

    suffix = _safe_logo_extension(upload.filename)
    assert suffix is not None

    safe_prefix = "".join(ch.lower() if ch.isalnum() else "-" for ch in prefix).strip("-") or "logo"
    filename = f"{safe_prefix}-{uuid4().hex[:12]}{suffix}"
    destination = _logo_upload_dir() / filename

    try:
        upload.file.seek(0)
        with destination.open("wb") as out_file:
            while chunk := upload.file.read(1024 * 1024):
                out_file.write(chunk)
    finally:
        upload.file.close()

    return filename


SORT_COLUMNS = {
    "company": Company.name,
    "position": JobApplication.position_title,
    "status": JobApplication.status,
    "source": JobApplication.source,
    "remote_policy": JobApplication.remote_policy,
    "applied": JobApplication.date_applied,
    "next_action": JobApplication.next_action_date,
    "location": func.coalesce(Company.city, JobApplication.location),
}


def _clean_filter(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _active_filter_params(
    q: str | None,
    status: str | None,
    position: str | None,
    source: str | None,
    remote_policy: str | None,
    location: str | None,
) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, value in {
        "q": q,
        "status": status,
        "position": position,
        "source": source,
        "remote_policy": remote_policy,
        "location": location,
    }.items():
        if value:
            params[key] = value
    return params


def _build_sort_urls(
    base_path: str,
    q: str | None,
    status: str | None,
    position: str | None,
    source: str | None,
    remote_policy: str | None,
    location: str | None,
    current_sort: str,
    current_direction: str,
) -> dict[str, str]:
    urls = {}
    active_filters = _active_filter_params(q, status, position, source, remote_policy, location)
    for column in SORT_COLUMNS:
        next_direction = "desc" if current_sort == column and current_direction == "asc" else "asc"
        params = {**active_filters, "sort": column, "direction": next_direction}
        urls[column] = f"{base_path}?" + urlencode(params)
    return urls


def _distinct_values(db: Session, column) -> list[str]:
    values = db.scalars(
        select(column)
        .where(column.is_not(None), column != "")
        .distinct()
        .order_by(column.asc())
    ).all()
    return [value for value in values if value]


def _status_options(db: Session, include_value: str | None = None) -> list[str]:
    values = list(
        db.scalars(
            select(JobStatus.name)
            .order_by(JobStatus.display_order.asc(), JobStatus.name.asc())
        ).all()
    )
    if not values:
        values = DEFAULT_STATUS_OPTIONS.copy()
    if include_value and include_value not in values:
        values.append(include_value)
    return values


def _status_options_for_stage(db: Session, stage: str, include_value: str | None = None) -> list[str]:
    values = list(
        db.scalars(
            select(JobStatus.name)
            .where(JobStatus.pipeline_stage == stage)
            .order_by(JobStatus.display_order.asc(), JobStatus.name.asc())
        ).all()
    )
    if not values:
        if stage == "interview":
            values = [status for status in DEFAULT_STATUS_OPTIONS if status in INTERVIEW_STATUS_DEFAULTS]
        else:
            values = [status for status in DEFAULT_STATUS_OPTIONS if status not in INTERVIEW_STATUS_DEFAULTS]
    if include_value and include_value not in values:
        values.append(include_value)
    return values


def _pipeline_stage_label(stage: str) -> str:
    return PIPELINE_STAGE_LABELS.get(stage, stage.title())


def _default_status(db: Session) -> str:
    options = _status_options(db)
    return options[0] if options else "Interested"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _companies_for_select(db: Session) -> list[Company]:
    return list(db.scalars(select(Company).order_by(Company.name.asc())).all())


def _contacts_for_select(db: Session) -> list[Contact]:
    return list(
        db.scalars(
            select(Contact)
            .options(selectinload(Contact.company))
            .outerjoin(Company)
            .order_by(Company.name.asc().nulls_last(), Contact.name.asc())
        ).all()
    )


def _recruiter_companies_for_select(db: Session) -> list[RecruiterCompany]:
    return list(db.scalars(select(RecruiterCompany).order_by(RecruiterCompany.name.asc())).all())


def _recruiter_company_or_none(db: Session, recruiter_company_id: int | None) -> RecruiterCompany | None:
    if not recruiter_company_id:
        return None
    recruiter_company = db.get(RecruiterCompany, recruiter_company_id)
    if not recruiter_company:
        raise HTTPException(status_code=400, detail="Selected recruiter company was not found")
    return recruiter_company


def _company_or_404(db: Session, company_id: int | None) -> Company:
    if not company_id:
        raise HTTPException(status_code=400, detail="Company is required")
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=400, detail="Selected company was not found")
    return company


def _selected_contacts(db: Session, contact_ids: list[int] | None) -> list[Contact]:
    if not contact_ids:
        return []
    unique_ids = sorted(set(contact_ids))
    return list(db.scalars(select(Contact).where(Contact.id.in_(unique_ids)).order_by(Contact.name.asc())).all())


def _sync_legacy_company_fields(application: JobApplication, company: Company) -> None:
    application.company_id = company.id
    application.company = company
    application.company_name = company.name
    application.company_website = company.website
    application.company_linkedin_url = company.linkedin_url
    application.company_logo_filename = company.logo_filename


def _application_from_form(
    company: Company,
    position_title: str,
    location: str | None,
    remote_policy: str | None,
    job_url: str | None,
    source: str | None,
    status: str,
    date_applied: str | None,
    next_action_date: str | None,
    salary_range: str | None,
    description: str | None,
    notes: str | None,
) -> dict:
    return {
        "company_id": company.id,
        "company_name": company.name,
        "company_website": company.website,
        "company_linkedin_url": company.linkedin_url,
        "company_logo_filename": company.logo_filename,
        "position_title": position_title.strip(),
        "location": _clean_text(location),
        "remote_policy": _clean_text(remote_policy),
        "job_url": _clean_text(job_url),
        "source": _clean_text(source),
        "status": status,
        "date_applied": _parse_date(date_applied),
        "next_action_date": _parse_date(next_action_date),
        "salary_range": _clean_text(salary_range),
        "description": _clean_text(description),
        "notes": _clean_text(notes),
    }


@router.get("/")
def redirect_to_application_intake():
    return RedirectResponse(url="/applications/interviews", status_code=303)


def _list_applications_for_stage(
    stage: str,
    request: Request,
    db: Session,
    q: str | None = None,
    status: str | None = None,
    position: str | None = None,
    source: str | None = None,
    remote_policy: str | None = None,
    location: str | None = None,
    sort: str | None = None,
    direction: str = "desc",
):
    q = _clean_filter(q)
    status = _clean_filter(status)
    position = _clean_filter(position)
    source = _clean_filter(source)
    remote_policy = _clean_filter(remote_policy)
    location = _clean_filter(location)

    stage_status_options = _status_options_for_stage(db, stage, status)

    stmt = (
        select(JobApplication)
        .outerjoin(Company)
        .options(selectinload(JobApplication.company), selectinload(JobApplication.contacts).selectinload(Contact.company))
    )

    if status:
        stmt = stmt.where(JobApplication.status == status)
    elif stage_status_options:
        stmt = stmt.where(JobApplication.status.in_(stage_status_options))

    if position:
        stmt = stmt.where(JobApplication.position_title == position)
    if source:
        stmt = stmt.where(JobApplication.source == source)
    if remote_policy:
        stmt = stmt.where(JobApplication.remote_policy == remote_policy)
    if location:
        stmt = stmt.where(or_(Company.city == location, JobApplication.location == location))
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Company.name.ilike(pattern),
                Company.website.ilike(pattern),
                Company.linkedin_url.ilike(pattern),
                Company.address.ilike(pattern),
                Company.city.ilike(pattern),
                JobApplication.company_name.ilike(pattern),
                JobApplication.position_title.ilike(pattern),
                JobApplication.location.ilike(pattern),
                JobApplication.source.ilike(pattern),
                JobApplication.remote_policy.ilike(pattern),
                JobApplication.job_url.ilike(pattern),
                JobApplication.notes.ilike(pattern),
            )
        )

    current_sort = sort if sort in SORT_COLUMNS else "applied"
    if current_sort == "updated_at":
        stmt = stmt.order_by(JobApplication.updated_at.desc())
    else:
        sort_column = SORT_COLUMNS[current_sort]
        order_clause = sort_column.asc() if direction == "asc" else sort_column.desc()
        stmt = stmt.order_by(order_clause.nulls_last(), JobApplication.updated_at.desc())

    applications = db.scalars(stmt).all()

    list_action = "/applications/interviews" if stage == "interview" else "/applications/intake"
    filter_options = {
        "status_options": stage_status_options,
        "position_options": _distinct_values(db, JobApplication.position_title),
        "source_options": _distinct_values(db, JobApplication.source),
        "remote_policy_options": _distinct_values(db, JobApplication.remote_policy),
        "location_options": sorted(set(_distinct_values(db, Company.city) + _distinct_values(db, JobApplication.location))),
    }

    return templates.TemplateResponse(
        request=request,
        name="job_list.html",
        context={
            "applications": applications,
            **filter_options,
            "selected_status": status or "",
            "selected_position": position or "",
            "selected_source": source or "",
            "selected_remote_policy": remote_policy or "",
            "selected_location": location or "",
            "q": q or "",
            "sort": current_sort,
            "direction": direction,
            "sort_urls": _build_sort_urls(list_action, q, status, position, source, remote_policy, location, current_sort, direction),
            "list_action": list_action,
            "clear_url": list_action,
            "page_title": _pipeline_stage_label(stage),
            "page_description": PIPELINE_STAGE_DESCRIPTIONS.get(stage, "Track job applications."),
            "pipeline_stage": stage,
            "stage_links": PIPELINE_STAGE_OPTIONS,
        },
    )


@router.get("/applications/intake")
def list_application_intake(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    position: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    remote_policy: Annotated[str | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
    direction: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
):
    return _list_applications_for_stage(
        "intake", request, db, q, status, position, source, remote_policy, location, sort, direction
    )


@router.get("/applications/interviews")
def list_interview_pipeline(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    position: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    remote_policy: Annotated[str | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
    direction: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
):
    return _list_applications_for_stage(
        "interview", request, db, q, status, position, source, remote_policy, location, sort, direction
    )


@router.get("/applications/new")
def new_application(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="job_form.html",
        context={
            "application": None,
            "companies": _companies_for_select(db),
            "contacts": _contacts_for_select(db),
            "selected_contact_ids": set(),
            "status_options": _status_options(db),
            "remote_policy_options": REMOTE_POLICY_OPTIONS,
            "form_action": "/applications",
            "page_title": "Add job application",
            "today": date.today(),
        },
    )


@router.post("/applications")
def create_application(
    db: Annotated[Session, Depends(get_db)],
    company_id: Annotated[int, Form()],
    position_title: Annotated[str, Form()],
    location: Annotated[str | None, Form()] = None,
    remote_policy: Annotated[str | None, Form()] = None,
    job_url: Annotated[str | None, Form()] = None,
    source: Annotated[str | None, Form()] = None,
    status: Annotated[str, Form()] = "Interested",
    date_applied: Annotated[str | None, Form()] = None,
    next_action_date: Annotated[str | None, Form()] = None,
    contact_ids: Annotated[list[int] | None, Form()] = None,
    salary_range: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    if not date_applied:
        date_applied = date.today().isoformat()

    company = _company_or_404(db, company_id)
    payload = _application_from_form(
        company,
        position_title,
        location,
        remote_policy,
        job_url,
        source,
        status,
        date_applied,
        next_action_date,
        salary_range,
        description,
        notes,
    )
    application = JobApplication(**payload)
    application.contacts = _selected_contacts(db, contact_ids)
    db.add(application)
    db.commit()
    db.refresh(application)

    if notes:
        db.add(ApplicationEvent(job_application_id=application.id, event_type="Note", event_date=date.today(), note=notes))
        db.commit()

    return RedirectResponse(url=f"/applications/{application.id}", status_code=303)


@router.get("/applications/{application_id}")
def application_detail(request: Request, application_id: int, db: Annotated[Session, Depends(get_db)]):
    stmt = (
        select(JobApplication)
        .options(
            selectinload(JobApplication.company),
            selectinload(JobApplication.contacts).selectinload(Contact.company),
            selectinload(JobApplication.events),
        )
        .where(JobApplication.id == application_id)
    )
    application = db.scalar(stmt)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={
            "application": application,
            "event_type_options": EVENT_TYPE_OPTIONS,
        },
    )


@router.get("/applications/{application_id}/edit")
def edit_application(request: Request, application_id: int, db: Annotated[Session, Depends(get_db)]):
    application = db.scalar(
        select(JobApplication)
        .options(selectinload(JobApplication.contacts))
        .where(JobApplication.id == application_id)
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return templates.TemplateResponse(
        request=request,
        name="job_form.html",
        context={
            "application": application,
            "companies": _companies_for_select(db),
            "contacts": _contacts_for_select(db),
            "selected_contact_ids": {contact.id for contact in application.contacts},
            "status_options": _status_options(db, application.status),
            "remote_policy_options": REMOTE_POLICY_OPTIONS,
            "form_action": f"/applications/{application.id}/edit",
            "page_title": "Edit job application",
            "today": date.today(),
        },
    )


@router.post("/applications/{application_id}/edit")
def update_application(
    application_id: int,
    db: Annotated[Session, Depends(get_db)],
    company_id: Annotated[int, Form()],
    position_title: Annotated[str, Form()],
    location: Annotated[str | None, Form()] = None,
    remote_policy: Annotated[str | None, Form()] = None,
    job_url: Annotated[str | None, Form()] = None,
    source: Annotated[str | None, Form()] = None,
    status: Annotated[str, Form()] = "Interested",
    date_applied: Annotated[str | None, Form()] = None,
    next_action_date: Annotated[str | None, Form()] = None,
    contact_ids: Annotated[list[int] | None, Form()] = None,
    salary_range: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    application = db.get(JobApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    company = _company_or_404(db, company_id)
    old_status = application.status
    payload = _application_from_form(
        company,
        position_title,
        location,
        remote_policy,
        job_url,
        source,
        status,
        date_applied,
        next_action_date,
        salary_range,
        description,
        notes,
    )
    for key, value in payload.items():
        setattr(application, key, value)
    _sync_legacy_company_fields(application, company)
    application.contacts = _selected_contacts(db, contact_ids)

    if old_status != status:
        db.add(
            ApplicationEvent(
                job_application_id=application.id,
                event_type="Status Change",
                event_date=date.today(),
                note=f"Status changed from {old_status} to {status}",
            )
        )

    db.commit()
    return RedirectResponse(url=f"/applications/{application.id}", status_code=303)


@router.post("/applications/{application_id}/events")
def add_event(
    application_id: int,
    db: Annotated[Session, Depends(get_db)],
    event_type: Annotated[str, Form()] = "Note",
    event_date: Annotated[str | None, Form()] = None,
    note: Annotated[str, Form()] = "",
):
    application = db.get(JobApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    clean_note = note.strip()
    if clean_note:
        db.add(
            ApplicationEvent(
                job_application_id=application.id,
                event_type=event_type,
                event_date=_parse_date(event_date) or date.today(),
                note=clean_note,
            )
        )
        db.commit()

    return RedirectResponse(url=f"/applications/{application.id}", status_code=303)


@router.post("/applications/{application_id}/delete")
def delete_application(application_id: int, db: Annotated[Session, Depends(get_db)]):
    application = db.get(JobApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(application)
    db.commit()
    return RedirectResponse(url="/applications/intake", status_code=303)


@router.get("/maintenance")
def maintenance(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="maintenance.html",
        context={},
    )


@router.get("/maintenance/statuses")
def list_statuses(request: Request, db: Annotated[Session, Depends(get_db)]):
    statuses = db.scalars(select(JobStatus).order_by(JobStatus.display_order.asc(), JobStatus.name.asc())).all()
    application_counts = dict(
        db.execute(
            select(JobApplication.status, func.count())
            .group_by(JobApplication.status)
        ).all()
    )
    return templates.TemplateResponse(
        request=request,
        name="statuses.html",
        context={"statuses": statuses, "application_counts": application_counts, "pipeline_stage_labels": PIPELINE_STAGE_LABELS},
    )


@router.get("/maintenance/statuses/new")
def new_status(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="status_form.html",
        context={
            "status_value": None,
            "form_action": "/maintenance/statuses",
            "page_title": "Add application status",
            "pipeline_stage_options": PIPELINE_STAGE_OPTIONS,
        },
    )


@router.post("/maintenance/statuses")
def create_status(
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    display_order: Annotated[int, Form()] = 0,
    pipeline_stage: Annotated[str, Form()] = "intake",
):
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Status name is required")
    existing = db.scalar(select(JobStatus).where(func.lower(JobStatus.name) == clean_name.lower()))
    if existing:
        raise HTTPException(status_code=400, detail="That status already exists")
    if pipeline_stage not in PIPELINE_STAGE_LABELS:
        raise HTTPException(status_code=400, detail="Invalid pipeline screen")
    status_value = JobStatus(name=clean_name, display_order=display_order, pipeline_stage=pipeline_stage)
    db.add(status_value)
    db.commit()
    return RedirectResponse(url="/maintenance/statuses", status_code=303)


@router.get("/maintenance/statuses/{status_id}/edit")
def edit_status(request: Request, status_id: int, db: Annotated[Session, Depends(get_db)]):
    status_value = db.get(JobStatus, status_id)
    if not status_value:
        raise HTTPException(status_code=404, detail="Status not found")
    return templates.TemplateResponse(
        request=request,
        name="status_form.html",
        context={
            "status_value": status_value,
            "form_action": f"/maintenance/statuses/{status_value.id}/edit",
            "page_title": "Edit application status",
            "pipeline_stage_options": PIPELINE_STAGE_OPTIONS,
        },
    )


@router.post("/maintenance/statuses/{status_id}/edit")
def update_status(
    status_id: int,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    display_order: Annotated[int, Form()] = 0,
    pipeline_stage: Annotated[str, Form()] = "intake",
):
    status_value = db.get(JobStatus, status_id)
    if not status_value:
        raise HTTPException(status_code=404, detail="Status not found")
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Status name is required")
    duplicate = db.scalar(
        select(JobStatus).where(func.lower(JobStatus.name) == clean_name.lower(), JobStatus.id != status_id)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="That status already exists")
    if pipeline_stage not in PIPELINE_STAGE_LABELS:
        raise HTTPException(status_code=400, detail="Invalid pipeline screen")
    old_name = status_value.name
    status_value.name = clean_name
    status_value.display_order = display_order
    status_value.pipeline_stage = pipeline_stage
    if old_name != clean_name:
        db.execute(update(JobApplication).where(JobApplication.status == old_name).values(status=clean_name))
    db.commit()
    return RedirectResponse(url="/maintenance/statuses", status_code=303)


@router.post("/maintenance/statuses/{status_id}/delete")
def delete_status(status_id: int, db: Annotated[Session, Depends(get_db)]):
    status_value = db.get(JobStatus, status_id)
    if not status_value:
        raise HTTPException(status_code=404, detail="Status not found")
    application_count = db.scalar(
        select(func.count()).select_from(JobApplication).where(JobApplication.status == status_value.name)
    )
    if application_count:
        raise HTTPException(
            status_code=400,
            detail="This status is still used by job applications. Reassign those applications first.",
        )
    db.delete(status_value)
    db.commit()
    return RedirectResponse(url="/maintenance/statuses", status_code=303)


@router.get("/companies")
def list_companies(request: Request, db: Annotated[Session, Depends(get_db)]):
    companies = db.scalars(
        select(Company)
        .options(selectinload(Company.contacts), selectinload(Company.applications))
        .order_by(Company.name.asc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="companies.html",
        context={"companies": companies},
    )


@router.get("/companies/new")
def new_company(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="company_form.html",
        context={
            "company": None,
            "form_action": "/companies",
            "page_title": "Add company",
        },
    )


@router.post("/companies")
def create_company(
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    website: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    address: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    logo_upload: Annotated[UploadFile | None, File()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    company = Company(
        name=name.strip(),
        website=_clean_text(website),
        linkedin_url=_clean_text(linkedin_url),
        address=_clean_text(address),
        city=_clean_text(city),
        notes=_clean_text(notes),
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    uploaded_logo = _save_logo_upload(logo_upload, f"company-{company.id}")
    if uploaded_logo:
        company.logo_filename = uploaded_logo
        db.commit()

    return RedirectResponse(url=f"/companies/{company.id}", status_code=303)


@router.get("/companies/{company_id}")
def company_detail(request: Request, company_id: int, db: Annotated[Session, Depends(get_db)]):
    company = db.scalar(
        select(Company)
        .options(selectinload(Company.contacts), selectinload(Company.applications))
        .where(Company.id == company_id)
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return templates.TemplateResponse(
        request=request,
        name="company_detail.html",
        context={"company": company},
    )


@router.get("/companies/{company_id}/edit")
def edit_company(request: Request, company_id: int, db: Annotated[Session, Depends(get_db)]):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return templates.TemplateResponse(
        request=request,
        name="company_form.html",
        context={
            "company": company,
            "form_action": f"/companies/{company.id}/edit",
            "page_title": "Edit company",
        },
    )


@router.post("/companies/{company_id}/edit")
def update_company(
    company_id: int,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    website: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    address: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    logo_upload: Annotated[UploadFile | None, File()] = None,
    remove_logo: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.name = name.strip()
    company.website = _clean_text(website)
    company.linkedin_url = _clean_text(linkedin_url)
    company.address = _clean_text(address)
    company.city = _clean_text(city)
    if remove_logo:
        company.logo_filename = None
    uploaded_logo = _save_logo_upload(logo_upload, f"company-{company.id}")
    if uploaded_logo:
        company.logo_filename = uploaded_logo
    company.notes = _clean_text(notes)

    for application in company.applications:
        _sync_legacy_company_fields(application, company)

    db.commit()
    return RedirectResponse(url=f"/companies/{company.id}", status_code=303)


@router.post("/companies/{company_id}/delete")
def delete_company(company_id: int, db: Annotated[Session, Depends(get_db)]):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    application_count = db.scalar(select(func.count()).select_from(JobApplication).where(JobApplication.company_id == company_id))
    contact_count = db.scalar(select(func.count()).select_from(Contact).where(Contact.company_id == company_id))
    if application_count or contact_count:
        raise HTTPException(
            status_code=400,
            detail="This company is still used by applications or contacts. Reassign or delete those records first.",
        )

    db.delete(company)
    db.commit()
    return RedirectResponse(url="/companies", status_code=303)


@router.get("/contacts")
def list_contacts(request: Request, db: Annotated[Session, Depends(get_db)]):
    contacts = _contacts_for_select(db)
    return templates.TemplateResponse(
        request=request,
        name="contacts.html",
        context={"contacts": contacts},
    )


@router.get("/contacts/new")
def new_contact(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={
            "contact": None,
            "companies": _companies_for_select(db),
            "form_action": "/contacts",
            "page_title": "Add contact",
        },
    )


@router.post("/contacts")
def create_contact(
    db: Annotated[Session, Depends(get_db)],
    company_id: Annotated[int, Form()],
    name: Annotated[str, Form()] = "",
    position: Annotated[str | None, Form()] = None,
    email: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    _company_or_404(db, company_id)
    contact = Contact(
        company_id=company_id,
        name=name.strip(),
        position=_clean_text(position),
        email=_clean_text(email),
        phone=_clean_text(phone),
        linkedin_url=_clean_text(linkedin_url),
        notes=_clean_text(notes),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return RedirectResponse(url=f"/contacts/{contact.id}", status_code=303)


@router.get("/contacts/{contact_id}")
def contact_detail(request: Request, contact_id: int, db: Annotated[Session, Depends(get_db)]):
    contact = db.scalar(
        select(Contact)
        .options(selectinload(Contact.company), selectinload(Contact.applications))
        .where(Contact.id == contact_id)
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return templates.TemplateResponse(
        request=request,
        name="contact_detail.html",
        context={"contact": contact},
    )


@router.get("/contacts/{contact_id}/edit")
def edit_contact(request: Request, contact_id: int, db: Annotated[Session, Depends(get_db)]):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={
            "contact": contact,
            "companies": _companies_for_select(db),
            "form_action": f"/contacts/{contact.id}/edit",
            "page_title": "Edit contact",
        },
    )


@router.post("/contacts/{contact_id}/edit")
def update_contact(
    contact_id: int,
    db: Annotated[Session, Depends(get_db)],
    company_id: Annotated[int, Form()],
    name: Annotated[str, Form()] = "",
    position: Annotated[str | None, Form()] = None,
    email: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    _company_or_404(db, company_id)
    contact.company_id = company_id
    contact.name = name.strip()
    contact.position = _clean_text(position)
    contact.email = _clean_text(email)
    contact.phone = _clean_text(phone)
    contact.linkedin_url = _clean_text(linkedin_url)
    contact.notes = _clean_text(notes)

    db.commit()
    return RedirectResponse(url=f"/contacts/{contact.id}", status_code=303)


@router.post("/contacts/{contact_id}/delete")
def delete_contact(contact_id: int, db: Annotated[Session, Depends(get_db)]):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.execute(delete(ApplicationContact).where(ApplicationContact.contact_id == contact.id))
    db.delete(contact)
    db.commit()
    return RedirectResponse(url="/contacts", status_code=303)


@router.get("/recruiter-companies")
def list_recruiter_companies(request: Request, db: Annotated[Session, Depends(get_db)]):
    recruiter_companies = db.scalars(
        select(RecruiterCompany)
        .options(selectinload(RecruiterCompany.contacts))
        .order_by(RecruiterCompany.name.asc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="recruiter_companies.html",
        context={"recruiter_companies": recruiter_companies},
    )


@router.get("/recruiter-companies/new")
def new_recruiter_company(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="recruiter_company_form.html",
        context={
            "recruiter_company": None,
            "form_action": "/recruiter-companies",
            "page_title": "Add recruiter company",
        },
    )


@router.post("/recruiter-companies")
def create_recruiter_company(
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    website: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    logo_upload: Annotated[UploadFile | None, File()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    recruiter_company = RecruiterCompany(
        name=name.strip(),
        website=_clean_text(website),
        linkedin_url=_clean_text(linkedin_url),
        notes=_clean_text(notes),
    )
    db.add(recruiter_company)
    db.commit()
    db.refresh(recruiter_company)

    uploaded_logo = _save_logo_upload(logo_upload, f"recruiter-company-{recruiter_company.id}")
    if uploaded_logo:
        recruiter_company.logo_filename = uploaded_logo
        db.commit()

    return RedirectResponse(url=f"/recruiter-companies/{recruiter_company.id}", status_code=303)


@router.get("/recruiter-companies/{recruiter_company_id}")
def recruiter_company_detail(request: Request, recruiter_company_id: int, db: Annotated[Session, Depends(get_db)]):
    recruiter_company = db.scalar(
        select(RecruiterCompany)
        .options(selectinload(RecruiterCompany.contacts))
        .where(RecruiterCompany.id == recruiter_company_id)
    )
    if not recruiter_company:
        raise HTTPException(status_code=404, detail="Recruiter company not found")
    return templates.TemplateResponse(
        request=request,
        name="recruiter_company_detail.html",
        context={"recruiter_company": recruiter_company},
    )


@router.get("/recruiter-companies/{recruiter_company_id}/edit")
def edit_recruiter_company(request: Request, recruiter_company_id: int, db: Annotated[Session, Depends(get_db)]):
    recruiter_company = db.get(RecruiterCompany, recruiter_company_id)
    if not recruiter_company:
        raise HTTPException(status_code=404, detail="Recruiter company not found")
    return templates.TemplateResponse(
        request=request,
        name="recruiter_company_form.html",
        context={
            "recruiter_company": recruiter_company,
            "form_action": f"/recruiter-companies/{recruiter_company.id}/edit",
            "page_title": "Edit recruiter company",
        },
    )


@router.post("/recruiter-companies/{recruiter_company_id}/edit")
def update_recruiter_company(
    recruiter_company_id: int,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    website: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    logo_upload: Annotated[UploadFile | None, File()] = None,
    remove_logo: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    recruiter_company = db.get(RecruiterCompany, recruiter_company_id)
    if not recruiter_company:
        raise HTTPException(status_code=404, detail="Recruiter company not found")

    recruiter_company.name = name.strip()
    recruiter_company.website = _clean_text(website)
    recruiter_company.linkedin_url = _clean_text(linkedin_url)
    if remove_logo:
        recruiter_company.logo_filename = None
    uploaded_logo = _save_logo_upload(logo_upload, f"recruiter-company-{recruiter_company.id}")
    if uploaded_logo:
        recruiter_company.logo_filename = uploaded_logo
    recruiter_company.notes = _clean_text(notes)
    db.commit()
    return RedirectResponse(url=f"/recruiter-companies/{recruiter_company.id}", status_code=303)


@router.post("/recruiter-companies/{recruiter_company_id}/delete")
def delete_recruiter_company(recruiter_company_id: int, db: Annotated[Session, Depends(get_db)]):
    recruiter_company = db.get(RecruiterCompany, recruiter_company_id)
    if not recruiter_company:
        raise HTTPException(status_code=404, detail="Recruiter company not found")

    contact_count = db.scalar(
        select(func.count()).select_from(RecruiterContact).where(
            RecruiterContact.recruiter_company_id == recruiter_company_id
        )
    )
    if contact_count:
        raise HTTPException(
            status_code=400,
            detail="This recruiter company still has recruiter contacts. Reassign or delete those contacts first.",
        )

    db.delete(recruiter_company)
    db.commit()
    return RedirectResponse(url="/recruiter-companies", status_code=303)


@router.get("/recruiter-contacts")
def list_recruiter_contacts(request: Request, db: Annotated[Session, Depends(get_db)]):
    recruiter_contacts = db.scalars(
        select(RecruiterContact)
        .options(selectinload(RecruiterContact.recruiter_company))
        .outerjoin(RecruiterCompany)
        .order_by(RecruiterCompany.name.asc().nulls_last(), RecruiterContact.name.asc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="recruiter_contacts.html",
        context={"recruiter_contacts": recruiter_contacts},
    )


@router.get("/recruiter-contacts/new")
def new_recruiter_contact(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="recruiter_contact_form.html",
        context={
            "recruiter_contact": None,
            "recruiter_companies": _recruiter_companies_for_select(db),
            "form_action": "/recruiter-contacts",
            "page_title": "Add recruiter contact",
        },
    )


@router.post("/recruiter-contacts")
def create_recruiter_contact(
    db: Annotated[Session, Depends(get_db)],
    recruiter_company_id: Annotated[int | None, Form()] = None,
    name: Annotated[str, Form()] = "",
    position: Annotated[str | None, Form()] = None,
    email: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    date_contact_made: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    _recruiter_company_or_none(db, recruiter_company_id)
    recruiter_contact = RecruiterContact(
        recruiter_company_id=recruiter_company_id or None,
        name=name.strip(),
        position=_clean_text(position),
        email=_clean_text(email),
        phone=_clean_text(phone),
        linkedin_url=_clean_text(linkedin_url),
        date_added=date.today(),
        date_contact_made=_parse_date(date_contact_made),
        notes=_clean_text(notes),
    )
    db.add(recruiter_contact)
    db.commit()
    db.refresh(recruiter_contact)
    return RedirectResponse(url=f"/recruiter-contacts/{recruiter_contact.id}", status_code=303)


@router.get("/recruiter-contacts/{recruiter_contact_id}")
def recruiter_contact_detail(request: Request, recruiter_contact_id: int, db: Annotated[Session, Depends(get_db)]):
    recruiter_contact = db.scalar(
        select(RecruiterContact)
        .options(selectinload(RecruiterContact.recruiter_company))
        .where(RecruiterContact.id == recruiter_contact_id)
    )
    if not recruiter_contact:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")
    return templates.TemplateResponse(
        request=request,
        name="recruiter_contact_detail.html",
        context={"recruiter_contact": recruiter_contact},
    )


@router.get("/recruiter-contacts/{recruiter_contact_id}/edit")
def edit_recruiter_contact(request: Request, recruiter_contact_id: int, db: Annotated[Session, Depends(get_db)]):
    recruiter_contact = db.get(RecruiterContact, recruiter_contact_id)
    if not recruiter_contact:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")
    return templates.TemplateResponse(
        request=request,
        name="recruiter_contact_form.html",
        context={
            "recruiter_contact": recruiter_contact,
            "recruiter_companies": _recruiter_companies_for_select(db),
            "form_action": f"/recruiter-contacts/{recruiter_contact.id}/edit",
            "page_title": "Edit recruiter contact",
        },
    )


@router.post("/recruiter-contacts/{recruiter_contact_id}/edit")
def update_recruiter_contact(
    recruiter_contact_id: int,
    db: Annotated[Session, Depends(get_db)],
    recruiter_company_id: Annotated[int | None, Form()] = None,
    name: Annotated[str, Form()] = "",
    position: Annotated[str | None, Form()] = None,
    email: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    linkedin_url: Annotated[str | None, Form()] = None,
    date_contact_made: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    recruiter_contact = db.get(RecruiterContact, recruiter_contact_id)
    if not recruiter_contact:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")

    _recruiter_company_or_none(db, recruiter_company_id)
    recruiter_contact.recruiter_company_id = recruiter_company_id or None
    recruiter_contact.name = name.strip()
    recruiter_contact.position = _clean_text(position)
    recruiter_contact.email = _clean_text(email)
    recruiter_contact.phone = _clean_text(phone)
    recruiter_contact.linkedin_url = _clean_text(linkedin_url)
    recruiter_contact.date_contact_made = _parse_date(date_contact_made)
    recruiter_contact.notes = _clean_text(notes)

    db.commit()
    return RedirectResponse(url=f"/recruiter-contacts/{recruiter_contact.id}", status_code=303)


@router.post("/recruiter-contacts/{recruiter_contact_id}/delete")
def delete_recruiter_contact(recruiter_contact_id: int, db: Annotated[Session, Depends(get_db)]):
    recruiter_contact = db.get(RecruiterContact, recruiter_contact_id)
    if not recruiter_contact:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")

    db.delete(recruiter_contact)
    db.commit()
    return RedirectResponse(url="/recruiter-contacts", status_code=303)
