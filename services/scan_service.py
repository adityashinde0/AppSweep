"""
Scan Service for discovering applications, computing deterministic content fingerprints,
and identifying duplicates with 64 KB memory-buffered chunked streaming.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import os
from pathlib import Path
import threading
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from core.models import (
    AppFile,
    Application,
    DuplicateGroup,
    DuplicateGroupMember,
    ScanJob,
)
from services.audit_service import record_audit
from services.rule_engine import RuleEvaluator

logger = logging.getLogger("JP001.ScanService")

# Active scan jobs cancellation registry
ACTIVE_SCAN_CANCELLATIONS: Dict[str, threading.Event] = {}


def compute_file_sha256(file_path: Path, chunk_size: int = settings.chunk_size) -> str:
    """
    Compute cryptographic SHA-256 hash using 64 KB memory-buffered streaming.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_application_fingerprint(files: List[Tuple[str, int, str]]) -> str:
    """
    Deterministic application-level content fingerprint derived from:
    sorted relative file paths + sizes + file SHA-256 hashes.
    Normalizes single-file apps so renamed duplicates match seamlessly.
    """
    if len(files) == 1:
        _, size, sha256_val = files[0]
        return hashlib.sha256(f"app:{size}:{sha256_val}".encode("utf-8")).hexdigest()

    # Sort files deterministically by relative path
    sorted_files = sorted(files, key=lambda item: item[0].replace("\\", "/").lower())
    fingerprint_hasher = hashlib.sha256()
    for rel_path, size, sha256_val in sorted_files:
        norm_rel = rel_path.replace("\\", "/").lower()
        line = f"{norm_rel}:{size}:{sha256_val}\n".encode("utf-8")
        fingerprint_hasher.update(line)
    return fingerprint_hasher.hexdigest()


class ScanWorker:
    """Background worker executing a scan job across configured roots."""

    def __init__(self, scan_job_id: str) -> None:
        self.scan_job_id = scan_job_id
        self.cancel_event = threading.Event()
        ACTIVE_SCAN_CANCELLATIONS[scan_job_id] = self.cancel_event

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def run(self) -> None:
        """Synchronous scan entry point run inside a background thread."""
        db: Session = SessionLocal()
        try:
            scan_job: Optional[ScanJob] = db.query(ScanJob).filter(ScanJob.id == self.scan_job_id).first()
            if not scan_job:
                logger.error("ScanJob '%s' not found in database", self.scan_job_id)
                return

            scan_job.status = "running"
            scan_job.started_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()

            record_audit(
                db,
                action="SCAN_STARTED",
                entity_type="scan_job",
                entity_id=self.scan_job_id,
                details={"roots": scan_job.roots},
            )

            rule_evaluator = RuleEvaluator(db)
            roots = [settings.sanitize_path(r) for r in scan_job.roots]

            # Validate roots against allowed roots
            for r in roots:
                if not settings.is_path_allowed(r):
                    raise PermissionError(f"Root directory '{r}' violates configured scan root boundaries.")
                if not r.exists() or not r.is_dir():
                    raise FileNotFoundError(f"Scan root directory does not exist: '{r}'")

            discovered_applications: List[Application] = []
            files_seen = 0
            error_count = 0

            # Set of recognized application bundle folders or standalone files
            for root_path in roots:
                if self.is_cancelled():
                    break

                for dirpath_str, dirnames, filenames in os.walk(str(root_path), topdown=True, followlinks=False):
                    if self.is_cancelled():
                        break

                    current_dir = Path(dirpath_str)

                    # Guard against symlink escape
                    try:
                        resolved_current = current_dir.resolve()
                        if not str(resolved_current).startswith(str(root_path.resolve())):
                            logger.warning("Skipping symlink escape: %s", current_dir)
                            dirnames.clear()
                            continue
                    except OSError:
                        error_count += 1
                        continue

                    # Treat each file as potential standalone application / artifact
                    for filename in filenames:
                        if self.is_cancelled():
                            break

                        file_path = current_dir / filename
                        files_seen += 1

                        try:
                            if not file_path.is_file() or file_path.is_symlink():
                                continue

                            stat_res = file_path.stat()
                            file_size = stat_res.st_size

                            # Compute streaming SHA-256 for file
                            file_hash = compute_file_sha256(file_path)
                            rel_path = file_path.name
                            app_fingerprint = compute_application_fingerprint([(rel_path, file_size, file_hash)])

                            app_name = file_path.name
                            category = rule_evaluator.categorize_application(
                                name=app_name,
                                path=file_path,
                                files=[{"relative_path": rel_path, "size": file_size, "sha256": file_hash}],
                            )

                            app_record = Application(
                                scan_job_id=self.scan_job_id,
                                name=app_name,
                                path=str(file_path.resolve()),
                                category=category,
                                content_fingerprint=app_fingerprint,
                                total_size=file_size,
                                file_count=1,
                                app_metadata={"extension": file_path.suffix.lower(), "parent_dir": str(current_dir)},
                            )
                            db.add(app_record)
                            db.flush()

                            # Save file record
                            app_file_record = AppFile(
                                application_id=app_record.id,
                                relative_path=rel_path,
                                size=file_size,
                                sha256=file_hash,
                            )
                            db.add(app_file_record)
                            discovered_applications.append(app_record)

                        except (PermissionError, FileNotFoundError, OSError) as file_err:
                            logger.warning("Error reading file '%s': %s", file_path, file_err)
                            error_count += 1

                        # Periodic flush and progress update
                        if files_seen % 50 == 0:
                            scan_job.files_seen = files_seen
                            scan_job.apps_found = len(discovered_applications)
                            scan_job.error_count = error_count
                            db.commit()

            if self.is_cancelled():
                scan_job.status = "cancelled"
                scan_job.completed_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
                record_audit(db, action="SCAN_CANCELLED", entity_type="scan_job", entity_id=self.scan_job_id)
                logger.info("Scan job '%s' was cancelled by user.", self.scan_job_id)
                return

            db.commit()

            # Group duplicates by content fingerprint
            logger.info("Grouping duplicates for scan job '%s'...", self.scan_job_id)
            fingerprint_map: Dict[str, List[Application]] = {}
            for app in discovered_applications:
                fingerprint_map.setdefault(app.content_fingerprint, []).append(app)

            duplicates_found_count = 0
            for fingerprint, apps_in_group in fingerprint_map.items():
                if len(apps_in_group) > 1:
                    duplicates_found_count += len(apps_in_group)
                    # Check or create DuplicateGroup
                    dup_group = db.query(DuplicateGroup).filter(DuplicateGroup.fingerprint == fingerprint).first()
                    if not dup_group:
                        dup_group = DuplicateGroup(fingerprint=fingerprint)
                        db.add(dup_group)
                        db.flush()

                    for member_app in apps_in_group:
                        existing_link = (
                            db.query(DuplicateGroupMember)
                            .filter(
                                DuplicateGroupMember.group_id == dup_group.id,
                                DuplicateGroupMember.application_id == member_app.id,
                            )
                            .first()
                        )
                        if not existing_link:
                            db.add(DuplicateGroupMember(group_id=dup_group.id, application_id=member_app.id))

            scan_job.status = "completed"
            scan_job.files_seen = files_seen
            scan_job.apps_found = len(discovered_applications)
            scan_job.duplicates_found = duplicates_found_count
            scan_job.error_count = error_count
            scan_job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()

            record_audit(
                db,
                action="SCAN_COMPLETED",
                entity_type="scan_job",
                entity_id=self.scan_job_id,
                details={
                    "files_seen": files_seen,
                    "apps_found": len(discovered_applications),
                    "duplicates_found": duplicates_found_count,
                    "error_count": error_count,
                },
            )
            logger.info(
                "Scan job '%s' completed successfully: %d files, %d apps, %d duplicates, %d errors.",
                self.scan_job_id, files_seen, len(discovered_applications), duplicates_found_count, error_count
            )

        except Exception as err:
            logger.error("Scan job '%s' failed with error: %s", self.scan_job_id, err, exc_info=True)
            db.rollback()
            try:
                scan_job = db.query(ScanJob).filter(ScanJob.id == self.scan_job_id).first()
                if scan_job:
                    scan_job.status = "failed"
                    scan_job.error_message = str(err)
                    scan_job.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    db.commit()
                record_audit(
                    db,
                    action="SCAN_FAILED",
                    entity_type="scan_job",
                    entity_id=self.scan_job_id,
                    details={"error": str(err)},
                )
            except Exception:
                pass
        finally:
            ACTIVE_SCAN_CANCELLATIONS.pop(self.scan_job_id, None)
            db.close()


def start_scan_job(scan_job_id: str) -> None:
    """Launch scan worker in a separate background daemon thread."""
    worker = ScanWorker(scan_job_id)
    thread = threading.Thread(target=worker.run, daemon=True, name=f"ScanWorker-{scan_job_id}")
    thread.start()


def cancel_scan_job(scan_job_id: str) -> bool:
    """Trigger cancellation for an active scan job."""
    cancel_evt = ACTIVE_SCAN_CANCELLATIONS.get(scan_job_id)
    if cancel_evt:
        cancel_evt.set()
        logger.info("Cancellation requested for scan job '%s'", scan_job_id)
        return True
    return False
