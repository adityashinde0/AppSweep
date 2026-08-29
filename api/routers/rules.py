"""
FastAPI router for categorization rule CRUD operations (/api/rules).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import CategorizationRule as RuleModel
from core.schemas import RuleCreate, RuleOut, RuleUpdate
from services.audit_service import record_audit

router = APIRouter(prefix="/api/rules", tags=["Rules"])


@router.get("", response_model=List[RuleOut])
def list_rules(db: Session = Depends(get_db)) -> List[RuleModel]:
    """
    List all categorization rules ordered by priority.
    """
    return db.query(RuleModel).order_by(RuleModel.priority.asc(), RuleModel.created_at.asc()).all()


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)) -> RuleModel:
    """
    Create a new dynamic application categorization rule.
    """
    rule = RuleModel(
        name=payload.name,
        priority=payload.priority,
        enabled=payload.enabled,
        conditions=payload.conditions,
        category=payload.category,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    record_audit(
        db,
        action="RULE_CREATED",
        entity_type="categorization_rule",
        entity_id=rule.id,
        details={"name": rule.name, "category": rule.category, "priority": rule.priority},
    )
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: str, payload: RuleUpdate, db: Session = Depends(get_db)) -> RuleModel:
    """
    Update an existing categorization rule's properties, conditions, or priority.
    """
    rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID '{rule_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(rule, field, val)

    db.commit()
    db.refresh(rule)

    record_audit(
        db,
        action="RULE_UPDATED",
        entity_type="categorization_rule",
        entity_id=rule.id,
        details=update_data,
    )
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: str, db: Session = Depends(get_db)) -> Response:
    """
    Delete a categorization rule.
    """
    rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID '{rule_id}' not found.",
        )

    db.delete(rule)
    db.commit()

    record_audit(
        db,
        action="RULE_DELETED",
        entity_type="categorization_rule",
        entity_id=rule_id,
        details={"name": rule.name},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
