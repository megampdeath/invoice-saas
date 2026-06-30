"""Supplier API routes (§7, §9 suppliers page)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.security import AuthContext, get_current_user
from app.db import models, session
from app.invoices import service

router = APIRouter(prefix="/api", tags=["suppliers"])


@router.get("/suppliers")
def list_suppliers(organization_id: str = Query(...),
                   auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    service._require_member(db, auth, organization_id)
    rows = db.execute(
        select(models.Supplier).where(models.Supplier.organization_id == uuid.UUID(organization_id))
        .order_by(models.Supplier.name)
    ).scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "vat_number": s.vat_number,
            "tax_id": s.tax_id,
            "iban": s.iban,
            "default_expense_category": s.default_expense_category,
        }
        for s in rows
    ]


class SupplierCreate:
    pass