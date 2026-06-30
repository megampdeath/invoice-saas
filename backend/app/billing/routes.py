"""Billing API routes (§7, §15)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import AuthContext, get_current_user
from app.db import session
from app.invoices import service
from app.billing import stripe_service, usage

router = APIRouter(prefix="/api", tags=["billing"])


class CheckoutRequest(BaseModel):
    organization_id: str
    plan: str  # starter | pro | business


@router.get("/organizations/{org_id}/usage")
def get_usage(org_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    service._require_member(db, auth, org_id)
    return usage.usage_summary(db, org_id)


@router.post("/billing/checkout")
def create_checkout(req: CheckoutRequest, auth: AuthContext = Depends(get_current_user),
                    db: Session = Depends(session.get_db)):
    org, member = service._require_member(db, auth, req.organization_id)
    if member.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners can manage billing")
    try:
        url = stripe_service.create_checkout_session(
            db, req.organization_id, req.plan,
            success_url=f"{settings.frontend_base_url}/app/settings?checkout=success",
            cancel_url=f"{settings.frontend_base_url}/app/settings?checkout=cancel",
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"url": url}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(session.get_db),
                         stripe_signature: str = Header(default="", alias="stripe-signature")):
    payload = await request.body()
    try:
        return stripe_service.handle_webhook(db, payload, stripe_signature)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Webhook error: {e}")