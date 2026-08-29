"""
SQLAlchemy database models for JP-001 Duplicate Application Manager.
Exact implementation of the 8 schema tables specified in ARCHITECTURE.md.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base


def generate_uuid() -> str:
    """Generate a standard UUID4 hex string."""
    return str(uuid.uuid4())


def utc_now() -> datetime.datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


class ScanJob(Base):
    """Represents an asynchronous scan job execution across configured roots."""
    __tablename__ = "scan_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    status = Column(String(20), nullable=False, default="queued")  # queued, running, completed, failed, cancelled
    roots = Column(JSON, nullable=False)  # list of root directory path strings
    files_seen = Column(BigInteger, default=0)
    apps_found = Column(Integer, default=0)
    duplicates_found = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    applications = relationship("Application", back_populates="scan_job", cascade="all, delete-orphan")


class Application(Base):
    """Represents a discovered standalone binary or multi-file application directory."""
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=True)
    name = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    category = Column(Text, nullable=True, default="Uncategorized")
    app_metadata = Column("metadata", JSON, default=dict)
    content_fingerprint = Column(Text, nullable=False, index=True)
    total_size = Column(BigInteger, default=0)
    file_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("scan_job_id", "path", name="uq_app_scan_path"),
        Index("applications_fingerprint_idx", "content_fingerprint"),
    )

    # Relationships
    scan_job = relationship("ScanJob", back_populates="applications")
    files = relationship("AppFile", back_populates="application", cascade="all, delete-orphan")
    duplicate_groups = relationship(
        "DuplicateGroup",
        secondary="duplicate_group_members",
        back_populates="members",
    )
    removals = relationship("RemovalAction", back_populates="application")


class AppFile(Base):
    """Represents a constituent file within an application."""
    __tablename__ = "app_files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    relative_path = Column(Text, nullable=False)
    size = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("application_id", "relative_path", name="uq_app_file_rel_path"),
    )

    # Relationships
    application = relationship("Application", back_populates="files")


class DuplicateGroupMember(Base):
    """Association table linking duplicate groups to member applications."""
    __tablename__ = "duplicate_group_members"

    group_id = Column(String(36), ForeignKey("duplicate_groups.id", ondelete="CASCADE"), primary_key=True)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)


class DuplicateGroup(Base):
    """Groups applications sharing identical content fingerprints."""
    __tablename__ = "duplicate_groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    fingerprint = Column(Text, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    members = relationship(
        "Application",
        secondary="duplicate_group_members",
        back_populates="duplicate_groups",
    )


class CategorizationRule(Base):
    """Configurable rule definitions for application categorization."""
    __tablename__ = "categorization_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(Text, nullable=False)
    priority = Column(Integer, default=100)
    enabled = Column(Boolean, default=True)
    conditions = Column(JSON, nullable=False)
    category = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class RemovalAction(Base):
    """Records quarantine and restore lifecycle operations for an application."""
    __tablename__ = "removal_actions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=True)
    action = Column(String(20), nullable=False)  # quarantine, restore
    original_path = Column(Text, nullable=False)
    quarantine_path = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    application = relationship("Application", back_populates="removals")


class AuditLog(Base):
    """Append-only audit trail capturing all system events and operations."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action = Column(Text, nullable=False)  # SCAN_START, SCAN_COMPLETE, QUARANTINE, RESTORE, RULE_CREATE, etc.
    entity_type = Column(Text, nullable=False)  # scan, application, duplicate_group, rule, removal
    entity_id = Column(String(36), nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now)
