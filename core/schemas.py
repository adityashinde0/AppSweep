"""
Pydantic schemas for API request and response validation.
Matches the exact schema definitions from ARCHITECTURE.md.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Scan Schemas
# ============================================================================

class ScanCreate(BaseModel):
    """Payload to initiate a new directory scan."""
    roots: List[str] = Field(..., min_length=1, description="List of local directory paths to scan")


class ScanJob(BaseModel):
    """Representation of an ongoing or completed scan job."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    roots: List[str]
    files_seen: int = 0
    apps_found: int = 0
    duplicates_found: int = 0
    error_count: int = 0
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime.datetime] = None


# ============================================================================
# Application & File Schemas
# ============================================================================

class AppFileOut(BaseModel):
    """Constituent file metadata within an application."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    relative_path: str
    size: int
    sha256: str


class ApplicationSummary(BaseModel):
    """High-level summary of a discovered application."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str
    category: Optional[str] = "Uncategorized"
    content_fingerprint: str
    total_size: int = 0
    file_count: int = 1
    created_at: Optional[datetime.datetime] = None


class ApplicationDetail(ApplicationSummary):
    """Detailed application view including all constituent files."""
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="app_metadata")
    files: List[AppFileOut] = Field(default_factory=list)


# ============================================================================
# Duplicate Group Schemas
# ============================================================================

class DuplicateGroupOut(BaseModel):
    """Summary of duplicate applications grouped by identical content fingerprint."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    fingerprint: str
    member_count: int
    total_size: int
    reclaimable_size: int
    category: Optional[str] = "Uncategorized"
    created_at: Optional[datetime.datetime] = None
    members: List[ApplicationSummary] = Field(default_factory=list)


class DuplicateGroupDetail(BaseModel):
    """Detailed view of a duplicate group with file-level evidence comparison."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    fingerprint: str
    member_count: int
    total_size: int
    reclaimable_size: int
    created_at: Optional[datetime.datetime] = None
    members: List[ApplicationDetail] = Field(default_factory=list)


# ============================================================================
# Removal & Quarantine Schemas
# ============================================================================

class RemovalPreviewRequest(BaseModel):
    """Request to preview the impact and target of a quarantine removal."""
    application_id: str


class RemovalPreview(BaseModel):
    """Safety preview details prior to confirming application quarantine."""
    application_id: str
    name: str
    original_path: str
    quarantine_destination: str
    total_size: int
    file_count: int
    is_safe: bool = True
    warnings: List[str] = Field(default_factory=list)


class RemovalCreate(BaseModel):
    """Payload to confirm and execute application quarantine."""
    application_id: str
    confirm: bool = Field(..., description="Must be explicitly True to proceed with quarantine")


class RemovalAction(BaseModel):
    """Record of a quarantine or restore action."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: Optional[str] = None
    action: Literal["quarantine", "restore"]
    original_path: str
    quarantine_path: Optional[str] = None
    status: Literal["pending", "completed", "failed"]
    error_message: Optional[str] = None
    created_at: Optional[datetime.datetime] = None


# ============================================================================
# Categorization Rule Schemas
# ============================================================================

class RuleCreate(BaseModel):
    """Payload to create a new categorization rule."""
    name: str = Field(..., min_length=1)
    priority: int = 100
    enabled: bool = True
    conditions: Dict[str, Any] = Field(..., description="JSON object containing extensions, keywords, path_patterns")
    category: str = Field(..., min_length=1)


class RuleUpdate(BaseModel):
    """Payload to update an existing categorization rule."""
    name: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    conditions: Optional[Dict[str, Any]] = None
    category: Optional[str] = None


class RuleOut(BaseModel):
    """Categorization rule representation."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    priority: int
    enabled: bool
    conditions: Dict[str, Any]
    category: str
    created_at: Optional[datetime.datetime] = None


# ============================================================================
# Audit Log Schemas
# ============================================================================

class AuditLogOut(BaseModel):
    """Audit log entry representation."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime.datetime] = None
