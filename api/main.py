"""
Main FastAPI Application Entry Point for JP-001 Duplicate Application Manager.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from api.routers import apps, audit, duplicates, removals, rules, scans
from core.config import settings
from core.database import get_db, init_db
from core.models import Application, DuplicateGroup, RemovalAction, ScanJob

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("JP001.API")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler initializing DB tables and seeding rules on startup."""
    logger.info("Starting JP-001 Duplicate Application Manager...")
    init_db()
    yield
    logger.info("Shutting down JP-001 Duplicate Application Manager.")


app = FastAPI(
    title="JP-001 Duplicate Application Manager",
    version=settings.app_version,
    description="Intelligent content-fingerprint duplicate application management, categorization, and quarantine system.",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(scans.router)
app.include_router(apps.router)
app.include_router(duplicates.router)
app.include_router(removals.router)
app.include_router(rules.router)
app.include_router(audit.router)

# Mount Static Files for Stitch Web UI
static_dir = Path("./static").resolve()
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
def serve_ui() -> FileResponse:
    """Serve the single-page Stitch Web UI dashboard."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return FileResponse(str(static_dir / "index.html"))


@app.get("/api/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version, "app": settings.app_name}


@app.get("/api/stats", tags=["System"])
def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retrieve high-level system KPIs for the dashboard:
    total apps, duplicate groups, reclaimable space, quarantined count, and scan status.
    """
    total_apps = db.query(Application).count()
    total_scanned_bytes = sum(a.total_size for a in db.query(Application.total_size).all()) or 0

    duplicate_groups = db.query(DuplicateGroup).all()
    dup_group_count = len(duplicate_groups)
    reclaimable_bytes = 0
    duplicate_app_count = 0

    for grp in duplicate_groups:
        members = grp.members
        if len(members) > 1:
            duplicate_app_count += len(members)
            single_size = members[0].total_size if members else 0
            reclaimable_bytes += (len(members) - 1) * single_size

    quarantined_count = (
        db.query(RemovalAction)
        .filter(RemovalAction.action == "quarantine", RemovalAction.status == "completed")
        .count()
    )

    recent_scan = db.query(ScanJob).order_by(ScanJob.created_at.desc()).first()

    return {
        "total_applications": total_apps,
        "total_scanned_bytes": total_scanned_bytes,
        "duplicate_groups_count": dup_group_count,
        "duplicate_applications_count": duplicate_app_count,
        "reclaimable_bytes": reclaimable_bytes,
        "quarantined_count": quarantined_count,
        "latest_scan": {
            "id": recent_scan.id,
            "status": recent_scan.status,
            "files_seen": recent_scan.files_seen,
            "apps_found": recent_scan.apps_found,
            "duplicates_found": recent_scan.duplicates_found,
            "error_count": recent_scan.error_count,
        } if recent_scan else None,
    }
