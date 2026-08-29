"""
Structured audit logging service.
Records all scan, quarantine, restore, and rule modifications to the database audit trail.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.models import AuditLog

logger = logging.getLogger("JP001.Audit")


def record_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Append an event to the audit log table.
    """
    log_entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    logger.info("AUDIT [%s] on %s (%s): %s", action, entity_type, entity_id, details)
    return log_entry
