"""Stripe checkout + webhook handling (§15).

Handles: checkout.session.completed, customer.subscription.created/updated/deleted,
invoice.payment_failed, invoice.payment_succeeded.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models

logger = logging.getLogger(__name__)


def _stripe():
    import stripe
    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout_session(db: Session, org_id: str, plan: str, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session for upgrading to `plan`."""
    if plan not in ("starter", "pro", "business"):
        raise ValueError("Invalid plan")
    env_key = PLAN_PRICE_ENV[plan]
    price_id = getattr(settings, env_key, "")
    if not price_id:
        raise RuntimeError(f"Stripe price for plan '{plan}' is not configured ({env_key})")

    org = db.get(models.Organization, _uuid(org_id))
    if not org:
        raise ValueError("Organization not found")

    stripe = _stripe()
    customer_id = org.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=org.billing_email or "", metadata={"org_id": str(org.id)})
        customer_id = customer.id
        org.stripe_customer_id = customer_id
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"org_id": str(org.id), "plan": plan},
    )
    return session.url


def handle_webhook(db: Session, payload: bytes, signature: str) -> dict:
    stripe = _stripe()
    event = stripe.Webhook.construct_event(
        payload, signature, settings.stripe_webhook_secret,
    )
    etype = event["type"]
    data = event["data"]["object"]

    if etype == "checkout.session.completed":
        _on_checkout(db, data)
    elif etype in ("customer.subscription.created", "customer.subscription.updated"):
        _on_subscription_change(db, data)
    elif etype == "customer.subscription.deleted":
        _on_subscription_deleted(db, data)
    elif etype == "invoice.payment_succeeded":
        logger.info("Stripe payment succeeded: %s", data.get("id"))
    elif etype == "invoice.payment_failed":
        _on_payment_failed(db, data)

    return {"received": True, "type": etype}


def _on_checkout(db: Session, session) -> None:
    org_id = session.get("metadata", {}).get("org_id")
    plan = session.get("metadata", {}).get("plan")
    if not org_id:
        return
    org = db.get(models.Organization, _uuid(org_id))
    if not org:
        return
    if session.get("customer"):
        org.stripe_customer_id = session["customer"]
    if session.get("subscription"):
        org.stripe_subscription_id = session["subscription"]
    if plan:
        org.plan = plan
    org.subscription_status = "active"
    db.add(models.AuditLog(
        organization_id=org.id, action="billing.plan_changed",
        target_type="organization", target_id=org.id,
        metadata_json={"plan": plan},
    ))
    db.commit()


def _on_subscription_change(db: Session, sub) -> None:
    sub_id = sub.get("id")
    org = _find_org_by_subscription(db, sub_id) or _find_org_by_customer(db, sub.get("customer"))
    if not org:
        return
    org.stripe_subscription_id = sub_id
    status = sub.get("status", "active")
    # Map Stripe status to our subscription_status
    org.subscription_status = status if status in ("active", "past_due", "canceled", "unpaid", "trialing") else "active"
    price_id = (sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id"))
    org.plan = _plan_from_price(price_id) or org.plan
    db.commit()


def _on_subscription_deleted(db: Session, sub) -> None:
    org = _find_org_by_subscription(db, sub.get("id"))
    if org:
        org.plan = "free"
        org.subscription_status = "canceled"
        org.stripe_subscription_id = None
        db.commit()


def _on_payment_failed(db: Session, invoice) -> None:
    org = _find_org_by_subscription(db, invoice.get("subscription")) or \
        _find_org_by_customer(db, invoice.get("customer"))
    if org:
        org.subscription_status = "past_due"
        db.commit()


def _find_org_by_subscription(db: Session, sub_id: Optional[str]):
    if not sub_id:
        return None
    from sqlalchemy import select
    return db.execute(select(models.Organization).where(
        models.Organization.stripe_subscription_id == sub_id)).scalar_one_or_none()


def _find_org_by_customer(db: Session, customer_id: Optional[str]):
    if not customer_id:
        return None
    from sqlalchemy import select
    return db.execute(select(models.Organization).where(
        models.Organization.stripe_customer_id == customer_id)).scalar_one_or_none()


def _plan_from_price(price_id: Optional[str]) -> Optional[str]:
    if not price_id:
        return None
    for plan, env in PLAN_PRICE_ENV.items():
        if getattr(settings, env, "") == price_id:
            return plan
    return None


def _uuid(value):
    import uuid as _u
    return value if isinstance(value, _u.UUID) else _u.UUID(str(value))


# late import to avoid cycle with billing.usage
from app.billing.usage import PLAN_PRICE_ENV  # noqa: E402