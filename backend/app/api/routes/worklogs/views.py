import uuid
from typing import Any, Optional

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.worklogs import service
from app.models import (
    RemittanceCreate,
    RemittanceResponse,
    RemittancesResponse,
    TimeEntryCreate,
    TimeEntryResponse,
    WorkLogCreate,
    WorkLogDetailResponse,
    WorkLogResponse,
    WorkLogsResponse,
)

router = APIRouter(tags=["worklogs"])


@router.get("/list-all-worklogs", response_model=WorkLogsResponse)
def list_all_worklogs(
    session: SessionDep,
    current_user: CurrentUser,
    startDate: Optional[str] = None,
    endDate: Optional[str] = None,
    remittanceStatus: Optional[str] = None,
) -> Any:
    """
    List all worklogs with total earnings per task.
    Optional filters:
      startDate / endDate  — ISO datetime strings for the worklog creation window
      remittanceStatus     — REMITTED or UNREMITTED
    """
    from datetime import datetime

    start_dt = None
    end_dt = None
    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid startDate format")
    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid endDate format")

    return service.list_worklogs(session, start_dt, end_dt, remittanceStatus, current_user)


@router.get("/worklogs/{worklog_id}", response_model=WorkLogDetailResponse)
def get_worklog(
    session: SessionDep,
    current_user: CurrentUser,
    worklog_id: uuid.UUID,
) -> Any:
    """
    Retrieve a single worklog and all its time entries.
    """
    return service.get_worklog(session, worklog_id)


@router.post(
    "/generate-remittances-for-all-users",
    response_model=list[RemittanceResponse],
    status_code=201,
)
def generate_remittances(
    session: SessionDep,
    current_user: CurrentUser,
    payload: RemittanceCreate,
) -> Any:
    """
    Generate remittances for a selected set of worklogs grouped by freelancer.
    Worklogs already remitted are rejected. One Remittance is created per freelancer.
    """
    return service.create_remittances(session, payload)


@router.get("/remittances", response_model=RemittancesResponse)
def list_remittances(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    List all remittances with freelancer info and worklog counts.
    """
    return service.list_remittances(session)


@router.post("/worklogs", response_model=WorkLogResponse, status_code=201)
def create_worklog(
    session: SessionDep,
    current_user: CurrentUser,
    payload: WorkLogCreate,
) -> Any:
    """
    Create a new worklog for the authenticated user (freelancer).
    The worklog is automatically assigned to the requesting user.
    """
    return service.create_worklog(session, current_user, payload)


@router.post(
    "/worklogs/{worklog_id}/time-entries",
    response_model=TimeEntryResponse,
    status_code=201,
)
def add_time_entry(
    session: SessionDep,
    current_user: CurrentUser,
    worklog_id: uuid.UUID,
    payload: TimeEntryCreate,
) -> Any:
    """
    Log a time entry against an existing worklog.
    Only the worklog owner (or a superuser) can add entries.
    Remitted worklogs are locked.
    """
    return service.add_time_entry(session, current_user, worklog_id, payload)
