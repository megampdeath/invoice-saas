"""Plan limits + usage tracking (§15).

Usage is counted when extraction begins (not at upload). Each organization has a
billing period (usage_period_start/end). We count `invoice_uploaded` events and
enforce the plan limit before extraction starts.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.core.config import settings

logger = logging.getLogger(__name__)

PLAN_LIMITS = {
    "free": 20,
    "starter": 200,
    "pro": 1000,
    "business": 100000,  # custom/high
}

PLAN_PRICE_ENV = {
    "starter": "stripe_price_starter_monthly",
    "pro": "stripe_price_pro_monthly",
    "business": "stripe_price_business_monthly",
}


class PlanLimitExceeded(Exception):
    pass


def get_plan_limit(plan: str) -> int:
    return PLAN_LIMITS.get(plan or "free", PLAN_LIMITS["free"])


def current_usage(db: Session, org_id) -> int:
    """Count invoice_uploaded usage events in the current billing period."""
    org_id = _uuid(org_id)
    org = db.get(models.Organization, org_id)
    start, end = _billing_window(org)
    q = select(func.coalesce(func.sum(models.UsageEvent.quantity), 0)).where(
        models.UsageEvent.organization_id == org_id,
        models.UsageEvent.event_type == "invoice_uploaded",
        models.UsageEvent.created_at >= start,
        models.UsageEvent.created_at < end,
    )
    return int(db.execute(q).scalar() or 0)


def _billing_window(org: Optional[models.Organization]) -> tuple[date, date]:
    today = date.today()
    if org and org.usage_period_start and org.usage_period_end:
        return org.usage_period_start, org.usage_period_end
    # default monthly window starting on the 1st
    start = today.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def record_usage(db: Session, org_id, event_type: str, quantity: int = 1, metadata: Optional[dict] = None) -> None:
    db.add(models.UsageEvent(
        organization_id=_uuid(org_id),
        event_type=event_type,
        quantity=quantity,
        metadata_json=metadata,
    ))
    db.commit()


def enforce_plan_limit(db: Session, org_id) -> None:
    org = db.get(models.Organization, _uuid(org_id))
    if not org:
        raise PlanLimitExceeded("Organization not found")
    # Past-due grace: keep read/export but block new extraction.
    if org.subscription_status in ("past_due", "canceled", "unpaid"):
        raise PlanLimitExceeded("Subscription is not active. Update billing to resume extraction.")
    used = current_usage(db, org.id)
    limit = get_plan_limit(org.plan)
    if used >= limit:
        raise PlanLimitExceeded(
            f"Plan limit reached ({used}/{limit} invoices this period). Upgrade to continue."
        )


def _uuid(value):
    import uuid as _u
    return value if isinstance(value, _u.UUID) else _u.UUID(str(value))


def usage_summary(db: Session, org_id) -> dict:
    org = db.get(models.Organization, _uuid(org_id))
    used = current_usage(db, org_id)
    limit = get_plan_limit(org.plan if org else "free")
    start, end = _billing_window(org)
    return {
        "plan": org.plan if org else "free",
        "subscription_status": org.subscription_status if org else "free",
        "used": used,
        "limit": limit,
        "usage_period_start": start.isoformat(),
        "usage_period_end": end.isoformat(),
    }