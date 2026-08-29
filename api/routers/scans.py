"""
FastAPI router for scan jobs (/api/scans).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.models import ScanJob as ScanJobModel
from core.schemas import ScanCreate, ScanJob as ScanJobOut
from services.scan_service import cancel_scan_job, start_scan_job

router = APIRouter(prefix="/api/scans", tags=["Scans"])


@router.post("", response_model=ScanJobOut, status_code=status.HTTP_201_CREATED)
def create_scan_job(payload: ScanCreate, db: Session = Depends(get_db)) -> ScanJobModel:
    """
    Launch a new background scan job over specified root directories.
    """
    for root in payload.roots:
        if not settings.is_path_allowed(root):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Root directory '{root}' violates configured allowed roots guardrails.",
            )

    scan_job = ScanJobModel(
        status="queued",
        roots=payload.roots,
    )
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)

    # Launch background scan thread
    start_scan_job(scan_job.id)

    return scan_job


@router.get("/{scan_id}", response_model=ScanJobOut)
def get_scan_job(scan_id: str, db: Session = Depends(get_db)) -> ScanJobModel:
    """
    Retrieve live status and metrics for a scan job.
    """
    scan_job = db.query(ScanJobModel).filter(ScanJobModel.id == scan_id).first()
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job with ID '{scan_id}' not found.",
        )
    return scan_job


@router.post("/{scan_id}/cancel", response_model=ScanJobOut)
def cancel_scan(scan_id: str, db: Session = Depends(get_db)) -> ScanJobModel:
    """
    Cancel an active or queued scan job.
    """
    scan_job = db.query(ScanJobModel).filter(ScanJobModel.id == scan_id).first()
    if not scan_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job with ID '{scan_id}' not found.",
        )

    if scan_job.status in ("completed", "failed", "cancelled"):
        return scan_job

    cancel_scan_job(scan_id)
    scan_job.status = "cancelled"
    db.commit()
    db.refresh(scan_job)

    return scan_job
