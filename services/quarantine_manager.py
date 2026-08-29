"""
Quarantine Manager service.
Handles safe removal (quarantine moves), safety checks, preview generation, and restoration.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.models import Application, RemovalAction
from core.schemas import RemovalPreview
from services.audit_service import record_audit

logger = logging.getLogger("JP001.QuarantineManager")


class QuarantineManager:
    """Manages moving applications into quarantine and restoring them."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def preview_removal(self, application_id: str) -> RemovalPreview:
        """
        Generate a safety preview before executing quarantine.
        """
        app = self.db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise ValueError(f"Application with ID '{application_id}' not found")

        app_path = settings.sanitize_path(app.path)
        warnings = []
        is_safe = True

        if not app_path.exists():
            warnings.append(f"Target path does not exist on disk: {app_path}")
            is_safe = False

        if not settings.is_path_allowed(app_path):
            warnings.append(f"Path '{app_path}' is outside configured allowed scan roots.")
            is_safe = False

        # Prepare planned quarantine destination
        target_name = app_path.name
        planned_quarantine = settings.quarantine_dir / application_id / target_name

        return RemovalPreview(
            application_id=app.id,
            name=app.name,
            original_path=str(app_path),
            quarantine_destination=str(planned_quarantine),
            total_size=app.total_size,
            file_count=app.file_count,
            is_safe=is_safe,
            warnings=warnings,
        )

    def quarantine_application(self, application_id: str, confirm: bool = False) -> RemovalAction:
        """
        Move an application into the quarantine directory with safety checks and audit logging.
        """
        if not confirm:
            raise ValueError("Quarantine operation rejected: Explicit user confirmation required (confirm=True)")

        app = self.db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise ValueError(f"Application with ID '{application_id}' not found")

        app_path = settings.sanitize_path(app.path)
        if not settings.is_path_allowed(app_path):
            raise PermissionError(f"Operation rejected: Path '{app_path}' violates allowed root guardrails.")

        if not app_path.exists():
            raise FileNotFoundError(f"Application file or directory not found on disk: {app_path}")

        # Construct destination directory
        target_name = app_path.name
        dest_dir = settings.quarantine_dir / application_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / target_name

        # Create pending removal record
        action_record = RemovalAction(
            application_id=app.id,
            action="quarantine",
            original_path=str(app_path),
            quarantine_path=str(dest_path),
            status="pending",
        )
        self.db.add(action_record)
        self.db.commit()
        self.db.refresh(action_record)

        try:
            # Atomic move into quarantine
            shutil.move(str(app_path), str(dest_path))
            action_record.status = "completed"
            self.db.commit()

            record_audit(
                self.db,
                action="APP_QUARANTINED",
                entity_type="application",
                entity_id=app.id,
                details={
                    "application_name": app.name,
                    "original_path": str(app_path),
                    "quarantine_path": str(dest_path),
                    "reclaimed_bytes": app.total_size,
                },
            )
            logger.info("Successfully quarantined application '%s' to '%s'", app.name, dest_path)
            return action_record
        except Exception as err:
            logger.error("Failed to move application '%s' to quarantine: %s", app.name, err)
            action_record.status = "failed"
            action_record.error_message = str(err)
            self.db.commit()

            record_audit(
                self.db,
                action="APP_QUARANTINE_FAILED",
                entity_type="application",
                entity_id=app.id,
                details={"error": str(err), "path": str(app_path)},
            )
            raise

    def restore_application(self, action_id: str) -> RemovalAction:
        """
        Restore a previously quarantined application back to its original location.
        """
        original_action = self.db.query(RemovalAction).filter(RemovalAction.id == action_id).first()
        if not original_action:
            raise ValueError(f"Removal action with ID '{action_id}' not found")

        if original_action.action != "quarantine" or original_action.status != "completed":
            raise ValueError("Only completed quarantine actions can be restored")

        quarantine_path = Path(original_action.quarantine_path).resolve()
        target_original_path = Path(original_action.original_path).resolve()

        if not quarantine_path.exists():
            raise FileNotFoundError(f"Quarantined files not found at '{quarantine_path}'")

        # Create restore action record
        restore_action = RemovalAction(
            application_id=original_action.application_id,
            action="restore",
            original_path=str(original_action.original_path),
            quarantine_path=str(quarantine_path),
            status="pending",
        )
        self.db.add(restore_action)
        self.db.commit()
        self.db.refresh(restore_action)

        try:
            # Recreate original parent directory if needed
            target_original_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(quarantine_path), str(target_original_path))

            # Clean up empty quarantine staging directory
            if quarantine_path.parent.exists() and not any(quarantine_path.parent.iterdir()):
                try:
                    quarantine_path.parent.rmdir()
                except OSError:
                    pass

            restore_action.status = "completed"
            self.db.commit()

            record_audit(
                self.db,
                action="APP_RESTORED",
                entity_type="application",
                entity_id=original_action.application_id,
                details={
                    "original_path": str(target_original_path),
                    "restored_from": str(quarantine_path),
                },
            )
            logger.info("Successfully restored application to '%s'", target_original_path)
            return restore_action
        except Exception as err:
            logger.error("Failed to restore application to '%s': %s", target_original_path, err)
            restore_action.status = "failed"
            restore_action.error_message = str(err)
            self.db.commit()

            record_audit(
                self.db,
                action="APP_RESTORE_FAILED",
                entity_type="application",
                entity_id=original_action.application_id,
                details={"error": str(err)},
            )
            raise
