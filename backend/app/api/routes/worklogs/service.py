import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    Remittance,
    RemittanceCreate,
    RemittanceResponse,
    RemittancesResponse,
    TimeEntry,
    TimeEntryCreate,
    TimeEntryResponse,
    User,
    WorkLog,
    WorkLogCreate,
    WorkLogDetailResponse,
    WorkLogResponse,
    WorkLogsResponse,
)

logger = logging.getLogger(__name__)


def _build_worklog_response(wl: WorkLog, session: Session) -> WorkLogResponse:
    """
    wl: worklog db row
    Returns a WorkLogResponse with computed total_earnings and freelancer info.
    """
    u = session.get(User, wl.user_id)
    entries = session.exec(
        select(TimeEntry).where(TimeEntry.worklog_id == wl.id)
    ).all()

    total = sum(e.hours * e.hourly_rate for e in entries if e.is_active)

    return WorkLogResponse(
        id=wl.id,
        task_name=wl.task_name,
        user_id=wl.user_id,
        status=wl.status,
        created_at=wl.created_at,
        remittance_id=wl.remittance_id,
        total_earnings=round(total, 2),
        freelancer_name=u.full_name if u else None,
        freelancer_email=u.email if u else "",
    )


def list_worklogs(
    session: Session,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    remittance_status: Optional[str],
    current_user: Optional[User] = None,
) -> WorkLogsResponse:
    """
    start_date: filter worklogs created on/after this date
    end_date: filter worklogs created on/before this date
    remittance_status: REMITTED or UNREMITTED
    current_user: if not superuser, scoped to their own worklogs only
    """
    stmt = select(WorkLog)

    # Regular users can only see their own work
    if current_user and not current_user.is_superuser:
        stmt = stmt.where(WorkLog.user_id == current_user.id)

    if start_date:
        stmt = stmt.where(WorkLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(WorkLog.created_at <= end_date)
    if remittance_status:
        if remittance_status not in ("REMITTED", "UNREMITTED"):
            raise HTTPException(
                status_code=400,
                detail="remittanceStatus must be REMITTED or UNREMITTED",
            )
        stmt = stmt.where(WorkLog.status == remittance_status)

    wls = session.exec(stmt).all()

    data = []
    for wl in wls:
        try:
            data.append(_build_worklog_response(wl, session))
        except Exception as e:
            logger.error(f"Failed to build response for worklog {wl.id}: {e}")
            continue

    return WorkLogsResponse(data=data, count=len(data))


def get_worklog(session: Session, wl_id: uuid.UUID) -> WorkLogDetailResponse:
    """
    wl_id: worklog primary key
    Returns worklog with all its time entries.
    """
    wl = session.get(WorkLog, wl_id)
    if not wl:
        raise HTTPException(status_code=404, detail="WorkLog not found")

    u = session.get(User, wl.user_id)
    entries = session.exec(
        select(TimeEntry).where(TimeEntry.worklog_id == wl.id)
    ).all()

    total = sum(e.hours * e.hourly_rate for e in entries if e.is_active)

    te_list = [
        TimeEntryResponse(
            id=e.id,
            worklog_id=e.worklog_id,
            description=e.description,
            hours=e.hours,
            hourly_rate=e.hourly_rate,
            recorded_at=e.recorded_at,
            is_active=e.is_active,
            amount=round(e.hours * e.hourly_rate, 2),
        )
        for e in entries
    ]

    return WorkLogDetailResponse(
        id=wl.id,
        task_name=wl.task_name,
        user_id=wl.user_id,
        status=wl.status,
        created_at=wl.created_at,
        remittance_id=wl.remittance_id,
        total_earnings=round(total, 2),
        freelancer_name=u.full_name if u else None,
        freelancer_email=u.email if u else "",
        time_entries=te_list,
    )


def create_remittances(
    session: Session, payload: RemittanceCreate
) -> list[RemittanceResponse]:
    """
    payload.worklog_ids: worklogs selected for payment
    payload.period_start / period_end: billing window
    Groups worklogs by freelancer, creates one Remittance per freelancer.
    """
    results = []

    # Fetch all selected worklogs
    wls = session.exec(
        select(WorkLog).where(WorkLog.id.in_(payload.worklog_ids))
    ).all()

    if not wls:
        raise HTTPException(status_code=400, detail="No valid worklogs found")

    # Reject any that are already remitted
    already_remitted = [wl for wl in wls if wl.status == "REMITTED"]
    if already_remitted:
        ids = [str(wl.id) for wl in already_remitted]
        raise HTTPException(
            status_code=409,
            detail=f"Some worklogs are already remitted: {ids}",
        )

    # Group by user_id
    by_user: dict[uuid.UUID, list[WorkLog]] = {}
    for wl in wls:
        by_user.setdefault(wl.user_id, []).append(wl)

    for u_id, user_wls in by_user.items():
        try:
            # Calculate total for this freelancer
            total = 0.0
            for wl in user_wls:
                entries = session.exec(
                    select(TimeEntry).where(TimeEntry.worklog_id == wl.id)
                ).all()
                total += sum(e.hours * e.hourly_rate for e in entries if e.is_active)

            u = session.get(User, u_id)

            # Create the remittance record
            r = Remittance(
                user_id=u_id,
                amount=round(total, 2),
                status="COMPLETED",
                period_start=payload.period_start,
                period_end=payload.period_end,
            )
            session.add(r)
            session.commit()
            session.refresh(r)

            # Mark worklogs as remitted
            for wl in user_wls:
                wl.status = "REMITTED"
                wl.remittance_id = r.id
                session.add(wl)

            session.commit()

            results.append(
                RemittanceResponse(
                    id=r.id,
                    user_id=r.user_id,
                    amount=r.amount,
                    status=r.status,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    created_at=r.created_at,
                    worklog_count=len(user_wls),
                    freelancer_name=u.full_name if u else None,
                    freelancer_email=u.email if u else "",
                )
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create remittance for user {u_id}: {e}")
            continue

    return results


def list_remittances(session: Session) -> RemittancesResponse:
    """Returns all remittances with freelancer info."""
    rs = session.exec(select(Remittance)).all()

    data = []
    for r in rs:
        try:
            u = session.get(User, r.user_id)
            wl_count = len(
                session.exec(
                    select(WorkLog).where(WorkLog.remittance_id == r.id)
                ).all()
            )
            data.append(
                RemittanceResponse(
                    id=r.id,
                    user_id=r.user_id,
                    amount=r.amount,
                    status=r.status,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    created_at=r.created_at,
                    worklog_count=wl_count,
                    freelancer_name=u.full_name if u else None,
                    freelancer_email=u.email if u else "",
                )
            )
        except Exception as e:
            logger.error(f"Failed to build remittance response {r.id}: {e}")
            continue

    return RemittancesResponse(data=data, count=len(data))


def create_worklog(
    session: Session, current_user: User, payload: WorkLogCreate
) -> WorkLogResponse:
    """
    current_user: the authenticated freelancer creating the worklog
    payload.task_name: name of the task being logged
    """
    wl = WorkLog(task_name=payload.task_name, user_id=current_user.id)
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return WorkLogResponse(
        id=wl.id,
        task_name=wl.task_name,
        user_id=wl.user_id,
        status=wl.status,
        created_at=wl.created_at,
        remittance_id=wl.remittance_id,
        total_earnings=0.0,
        freelancer_name=current_user.full_name,
        freelancer_email=current_user.email,
    )


def add_time_entry(
    session: Session,
    current_user: User,
    wl_id: uuid.UUID,
    payload: TimeEntryCreate,
) -> TimeEntryResponse:
    """
    current_user: must own the worklog (or be superuser)
    wl_id: the worklog to log time against
    payload: description, hours, hourly_rate
    """
    wl = session.get(WorkLog, wl_id)
    if not wl:
        raise HTTPException(status_code=404, detail="WorkLog not found")
    if not current_user.is_superuser and wl.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to log time on this worklog")
    if wl.status == "REMITTED":
        raise HTTPException(status_code=409, detail="Cannot add time to an already remitted worklog")

    te = TimeEntry(
        worklog_id=wl_id,
        description=payload.description,
        hours=payload.hours,
        hourly_rate=payload.hourly_rate,
    )
    session.add(te)
    session.commit()
    session.refresh(te)

    return TimeEntryResponse(
        id=te.id,
        worklog_id=te.worklog_id,
        description=te.description,
        hours=te.hours,
        hourly_rate=te.hourly_rate,
        recorded_at=te.recorded_at,
        is_active=te.is_active,
        amount=round(te.hours * te.hourly_rate, 2),
    )
