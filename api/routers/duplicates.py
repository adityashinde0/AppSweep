"""
FastAPI router for duplicate groups (/api/duplicates).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.models import Application as ApplicationModel, DuplicateGroup as DuplicateGroupModel
from core.schemas import (
    ApplicationDetail,
    ApplicationSummary,
    DuplicateGroupDetail,
    DuplicateGroupOut,
)

router = APIRouter(prefix="/api/duplicates", tags=["Duplicates"])


@router.get("", response_model=List[DuplicateGroupOut])
def list_duplicate_groups(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[DuplicateGroupOut]:
    """
    List duplicate groups with member count, total size, and reclaimable redundant space.
    """
    groups = (
        db.query(DuplicateGroupModel)
        .options(joinedload(DuplicateGroupModel.members))
        .order_by(DuplicateGroupModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results: List[DuplicateGroupOut] = []
    for grp in groups:
        members = grp.members
        if not members:
            continue

        member_count = len(members)
        single_app_size = members[0].total_size if members else 0
        total_size = sum(m.total_size for m in members)
        reclaimable_size = max(0, (member_count - 1) * single_app_size)
        primary_category = members[0].category if members else "Uncategorized"

        member_summaries = [
            ApplicationSummary(
                id=m.id,
                name=m.name,
                path=m.path,
                category=m.category,
                content_fingerprint=m.content_fingerprint,
                total_size=m.total_size,
                file_count=m.file_count,
                created_at=m.created_at,
            )
            for m in members
        ]

        results.append(
            DuplicateGroupOut(
                id=grp.id,
                fingerprint=grp.fingerprint,
                member_count=member_count,
                total_size=total_size,
                reclaimable_size=reclaimable_size,
                category=primary_category,
                created_at=grp.created_at,
                members=member_summaries,
            )
        )

    return results


@router.get("/{group_id}", response_model=DuplicateGroupDetail)
def get_duplicate_group_detail(group_id: str, db: Session = Depends(get_db)) -> DuplicateGroupDetail:
    """
    Retrieve full details for a duplicate group, including all members and constituent file manifests.
    """
    grp = (
        db.query(DuplicateGroupModel)
        .options(joinedload(DuplicateGroupModel.members).joinedload(ApplicationModel.files))
        .filter(DuplicateGroupModel.id == group_id)
        .first()
    )
    if not grp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Duplicate group with ID '{group_id}' not found.",
        )

    members = grp.members
    member_count = len(members)
    single_app_size = members[0].total_size if members else 0
    total_size = sum(m.total_size for m in members)
    reclaimable_size = max(0, (member_count - 1) * single_app_size)

    member_details = []
    for m in members:
        member_details.append(
            ApplicationDetail(
                id=m.id,
                name=m.name,
                path=m.path,
                category=m.category,
                content_fingerprint=m.content_fingerprint,
                total_size=m.total_size,
                file_count=m.file_count,
                metadata=m.app_metadata or {},
                created_at=m.created_at,
                files=[
                    {"id": f.id, "relative_path": f.relative_path, "size": f.size, "sha256": f.sha256}
                    for f in m.files
                ],
            )
        )

    return DuplicateGroupDetail(
        id=grp.id,
        fingerprint=grp.fingerprint,
        member_count=member_count,
        total_size=total_size,
        reclaimable_size=reclaimable_size,
        created_at=grp.created_at,
        members=member_details,
    )
