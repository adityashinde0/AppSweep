"""
FastAPI router for applications (/api/apps).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.models import Application as ApplicationModel
from core.schemas import ApplicationDetail, ApplicationSummary

router = APIRouter(prefix="/api/apps", tags=["Applications"])


@router.get("", response_model=List[ApplicationSummary])
def list_applications(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by application name or path"),
    scan_job_id: Optional[str] = Query(None, description="Filter by scan job ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[ApplicationModel]:
    """
    List discovered applications with optional category and search filters.
    """
    query = db.query(ApplicationModel)

    if category:
        query = query.filter(ApplicationModel.category == category)

    if scan_job_id:
        query = query.filter(ApplicationModel.scan_job_id == scan_job_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (ApplicationModel.name.ilike(search_pattern)) | (ApplicationModel.path.ilike(search_pattern))
        )

    applications = (
        query.order_by(ApplicationModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return applications


@router.get("/{app_id}", response_model=ApplicationDetail)
def get_application_detail(app_id: str, db: Session = Depends(get_db)) -> ApplicationModel:
    """
    Retrieve full details for an application, including its constituent file manifests.
    """
    application = (
        db.query(ApplicationModel)
        .options(joinedload(ApplicationModel.files))
        .filter(ApplicationModel.id == app_id)
        .first()
    )
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID '{app_id}' not found.",
        )
    return application
