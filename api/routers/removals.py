"""
FastAPI router for safe removal and quarantine operations (/api/removals).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import RemovalAction as RemovalActionModel
from core.schemas import (
    RemovalAction,
    RemovalCreate,
    RemovalPreview,
    RemovalPreviewRequest,
)
from services.quarantine_manager import QuarantineManager

router = APIRouter(prefix="/api/removals", tags=["Removals & Quarantine"])


@router.post("/preview", response_model=RemovalPreview)
def preview_quarantine(payload: RemovalPreviewRequest, db: Session = Depends(get_db)) -> RemovalPreview:
    """
    Generate a safety preview and target destination before confirming quarantine removal.
    """
    manager = QuarantineManager(db)
    try:
        return manager.preview_removal(payload.application_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("", response_model=RemovalAction, status_code=status.HTTP_201_CREATED)
def execute_quarantine(payload: RemovalCreate, db: Session = Depends(get_db)) -> RemovalActionModel:
    """
    Execute application quarantine move after explicit confirmation.
    """
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quarantine operation rejected: Explicit confirmation flag (confirm=True) is required.",
        )

    manager = QuarantineManager(db)
    try:
        return manager.quarantine_application(payload.application_id, confirm=payload.confirm)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (PermissionError, FileNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Quarantine failed: {err}")


@router.post("/{action_id}/restore", response_model=RemovalAction)
def restore_quarantine(action_id: str, db: Session = Depends(get_db)) -> RemovalActionModel:
    """
    Restore a previously quarantined application back to its original filesystem path.
    """
    manager = QuarantineManager(db)
    try:
        return manager.restore_application(action_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except FileNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Restoration failed: {err}")


@router.get("", response_model=List[RemovalAction])
def list_removal_actions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[RemovalActionModel]:
    """
    List all past quarantine and restoration operations.
    """
    actions = (
        db.query(RemovalActionModel)
        .order_by(RemovalActionModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return actions
