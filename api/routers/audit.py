"""
FastAPI router for audit logs (/api/audit).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AuditLog as AuditLogModel
from core.schemas import AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get("", response_model=List[AuditLogOut])
def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by audit action (e.g. SCAN_COMPLETED, APP_QUARANTINED)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[AuditLogModel]:
    """
    List structured audit logs capturing all scan, categorization, quarantine, and restore operations.
    """
    query = db.query(AuditLogModel)

    if action:
        query = query.filter(AuditLogModel.action == action)

    if entity_type:
        query = query.filter(AuditLogModel.entity_type == entity_type)

    logs = (
        query.order_by(AuditLogModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return logs
