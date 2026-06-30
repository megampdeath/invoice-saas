"""Invoice service: org authorization, upload, status transitions, review."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import AuthContext
from app.db import models
from app.invoices import normalization, validation
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

ALLOWED_MIME = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tiff",
}
MAX_FILE_SIZE = 25 * 1024 * 1024


class AuthorizationError(Exception):
    pass


class ValidationError(Exception):
    pass


def _require_member(db: Session, auth: AuthContext, org_id: str) -> tuple[models.Organization, models.OrganizationMember]:
    org = db.get(models.Organization, uuid.UUID(org_id))
    if not org:
        raise AuthorizationError("Organization not found")
    member = db.execute(
        select(models.OrganizationMember).where(
            models.OrganizationMember.organization_id == org.id,
            models.OrganizationMember.user_id == uuid.UUID(auth.user_id),
        )
    ).scalar_one_or_none()
    if not member:
        raise AuthorizationError("Not a member of this organization")
    return org, member


ROLES_CAN_UPLOAD = {"owner", "admin", "member"}
ROLES_CAN_EDIT = {"owner", "admin", "member"}
ROLES_CAN_APPROVE = {"owner", "admin", "member"}
ROLES_CAN_DELETE = {"owner", "owner"}


def ensure_user_profile(db: Session, auth: AuthContext) -> models.User:
    user = db.get(models.User, uuid.UUID(auth.user_id))
    if not user:
        user = models.User(id=uuid.UUID(auth.user_id), email=auth.email or f"{auth.user_id}@unknown")
        db.add(user)
        db.commit()
    return user


def ensure_default_organization(db: Session, auth: AuthContext) -> models.Organization | None:
    """Free signup onboarding: every new user gets a personal workspace at no cost.

    Returns the user's first organization, creating one if they have none. No
    payment is required — the org starts on the free plan (20 invoices/month).
    """
    user = ensure_user_profile(db, auth)
    existing = db.execute(
        select(models.OrganizationMember).where(models.OrganizationMember.user_id == user.id)
    ).scalars().all()
    if existing:
        return db.get(models.Organization, existing[0].organization_id)
    import re
    base = re.sub(r"[^a-z0-9-]+", "-", (user.email or "user").split("@")[0].lower()).strip("-") or "workspace"
    slug = base
    n = 1
    while db.execute(select(models.Organization).where(models.Organization.slug == slug)).scalar_one_or_none():
        n += 1
        slug = f"{base}-{n}"
    org = models.Organization(
        name=f"{user.email or 'My'}'s workspace",
        slug=slug,
        billing_email=user.email,
        plan="free",
        subscription_status="free",
    )
    db.add(org)
    db.flush()
    db.add(models.OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    return org


def build_storage_key(org_id: str, invoice_id: str, filename: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)
    safe = safe.lstrip(".")  # deny leading-dot traversal/dotfiles
    if not safe:
        safe = "invoice"
    return f"{org_id}/originals/{invoice_id}/{safe}"


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_file_url(invoice_id, expires_in: int = 600) -> str:
    """Short-lived, HMAC-signed URL for viewing an invoice file in an <iframe>/<img>.

    Returns a **relative** URL (`/api/invoices/{id}/file?exp=...&sig=...`) so the
    browser resolves it against the frontend's origin. The frontend proxies
    /api/* to the backend via a same-origin rewrite, which makes the file
    same-origin to the page — Chrome only renders inline PDFs in <iframe> when
    they are same-origin; cross-origin PDFs are force-downloaded or blanked.

    iframes/img tags cannot send a Bearer Authorization header, so the URL
    carries a short-lived HMAC token (signed with PREVIEW_TOKEN_SECRET) that the
    /api/invoices/{id}/file endpoint verifies. The token expires in 10 minutes.
    """
    import time, hmac
    exp = int(time.time()) + expires_in
    msg = f"file:{invoice_id}:{exp}".encode()
    sig = hmac.new((settings.preview_token_secret or "dev-secret").encode(), msg, hashlib.sha256).hexdigest()
    return f"/api/invoices/{invoice_id}/file?exp={exp}&sig={sig}"


def verify_file_token(invoice_id, exp: int, sig: str) -> bool:
    import time, hmac
    if int(time.time()) > int(exp):
        return False
    msg = f"file:{invoice_id}:{exp}".encode()
    expected = hmac.new((settings.preview_token_secret or "dev-secret").encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig or "")


def upload_invoice(
    db: Session, auth: AuthContext, org_id: str, file_name: str, mime_type: str, file_bytes: bytes, storage: StorageBackend
) -> models.Invoice:
    org, member = _require_member(db, auth, org_id)
    if member.role not in ROLES_CAN_UPLOAD:
        raise AuthorizationError("Your role cannot upload invoices")

    if mime_type not in ALLOWED_MIME:
        raise ValidationError(f"Unsupported file type: {mime_type}")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValidationError("File exceeds 25MB limit")

    ensure_user_profile(db, auth)

    # Enforce plan usage limit before extraction starts (§15)
    from app.billing import usage as _usage
    _usage.enforce_plan_limit(db, org.id)

    invoice_id = uuid.uuid4()
    doc_hash = compute_hash(file_bytes)
    storage_key = build_storage_key(org_id, str(invoice_id), file_name)
    storage.put(settings.supabase_storage_originals_bucket, storage_key, file_bytes, mime_type)

    # duplicate detection within org
    dup = db.execute(
        select(models.Invoice).where(
            models.Invoice.organization_id == org.id,
            models.Invoice.document_hash == doc_hash,
        )
    ).scalar_one_or_none()

    invoice = models.Invoice(
        id=invoice_id,
        organization_id=org.id,
        uploaded_by_user_id=uuid.UUID(auth.user_id),
        status="uploaded",
        original_filename=file_name,
        file_mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        storage_key=storage_key,
        document_hash=doc_hash,
        duplicate_of_invoice_id=dup.id if dup else None,
    )
    db.add(invoice)
    db.flush()  # ensure the invoice row exists before the job references it (no ORM relationship)

    job = models.ExtractionJob(
        invoice_id=invoice.id,
        status="queued",
        provider=settings.extraction_provider,
        queued_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()

    if dup:
        db.add(models.ExtractionWarning(
            invoice_id=invoice.id, code="duplicate_invoice_detected",
            severity="warning", message="A document with the same hash already exists.",
        ))
        db.commit()

    # Count usage when extraction begins (§15)
    from app.billing import usage as _usage
    _usage.record_usage(db, org.id, "invoice_uploaded", 1, {"invoice_id": str(invoice.id)})

    _enqueue_job(invoice.id, job.id)
    return invoice


def _enqueue_job(invoice_id: uuid.UUID, job_id: uuid.UUID) -> None:
    """Enqueue extraction. Falls back to inline processing when Redis is unavailable
    or not configured (dev mode)."""
    if settings.redis_url:
        try:
            from redis import Redis
            from rq import Queue
            q = Queue("invoices", connection=Redis.from_url(settings.redis_url))
            q.enqueue("app.workers.process_invoice.process_invoice_job", str(invoice_id), str(job_id))
            return
        except Exception as exc:
            logger.warning("Redis enqueue failed (%s); extracting inline", exc)
    # Inline fallback (dev / no Redis)
    from app.workers.process_invoice import process_invoice_job
    process_invoice_job(str(invoice_id), str(job_id))


def list_invoices(db: Session, auth: AuthContext, org_id: str, status: Optional[str] = None,
                  search: Optional[str] = None, page: int = 1, page_size: int = 25) -> dict:
    _require_member(db, auth, org_id)
    q = select(models.Invoice).where(models.Invoice.organization_id == uuid.UUID(org_id))
    if status:
        q = q.where(models.Invoice.status == status)
    total_q = select(models.Invoice).where(models.Invoice.organization_id == uuid.UUID(org_id))
    if status:
        total_q = total_q.where(models.Invoice.status == status)
    if search:
        like = f"%{search}%"
        q = q.where(models.Invoice.invoice_number.ilike(like))
        total_q = total_q.where(models.Invoice.invoice_number.ilike(like))
    from sqlalchemy import func
    total = db.execute(select(func.count()).select_from(total_q.subquery())).scalar() or 0
    offset = (page - 1) * page_size
    rows = db.execute(q.order_by(models.Invoice.created_at.desc()).offset(offset).limit(page_size)).scalars().all()
    return {"items": rows, "page": page, "page_size": page_size, "total": total}


def get_invoice_detail(db: Session, auth: AuthContext, invoice_id: str, storage: StorageBackend) -> dict:
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise ValidationError("Invoice not found")
    _require_member(db, auth, str(invoice.organization_id))
    warnings = db.execute(
        select(models.ExtractionWarning).where(models.ExtractionWarning.invoice_id == invoice.id)
    ).scalars().all()
    party = db.execute(
        select(models.InvoiceParty).where(
            models.InvoiceParty.invoice_id == invoice.id,
            models.InvoiceParty.party_type == "supplier",
        )
    ).scalar_one_or_none()
    url = build_file_url(invoice.id, expires_in=600)
    return {
        "id": str(invoice.id),
        "status": invoice.status,
        "original_filename": invoice.original_filename,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "currency": invoice.currency,
        "subtotal_amount": invoice.subtotal_amount,
        "tax_amount": invoice.tax_amount,
        "total_amount": invoice.total_amount,
        "iban": invoice.iban,
        "payment_terms": invoice.payment_terms,
        "supplier": {"name": party.name if party else None, "vat_number": party.vat_number if party else None},
        "confidence": float(invoice.extraction_confidence or 0),
        "warnings": [{"code": w.code, "message": w.message, "severity": w.severity} for w in warnings],
        "file_preview_url": url,
    }


def apply_extraction_result(db: Session, invoice_id: str, result_fields: dict, confidence: float,
                           warnings: list) -> None:
    """Persist normalized extraction fields + warnings, set status needs_review."""
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        return

    def val(name):
        v = result_fields.get(name)
        return getattr(v, "value", None) if v is not None else None

    invoice.invoice_number = val("invoice_number") or invoice.invoice_number
    if (d := normalization.normalize_date(val("invoice_date"))):
        invoice.invoice_date = d
    if (d := normalization.normalize_date(val("due_date"))):
        invoice.due_date = d
    invoice.currency = normalization.normalize_currency(val("currency")) or invoice.currency
    if (a := normalization.normalize_amount(val("subtotal_amount"))) is not None:
        invoice.subtotal_amount = a
    if (a := normalization.normalize_amount(val("tax_amount"))) is not None:
        invoice.tax_amount = a
    if (a := normalization.normalize_amount(val("total_amount"))) is not None:
        invoice.total_amount = a
    invoice.iban = val("iban") or invoice.iban
    invoice.raw_text = result_fields.get("__raw_text__") or ""
    invoice.extraction_confidence = confidence

    sup_name = normalization.normalize_supplier_name(val("supplier_name"))
    if sup_name:
        existing = db.execute(select(models.InvoiceParty).where(
            models.InvoiceParty.invoice_id == invoice.id,
            models.InvoiceParty.party_type == "supplier",
        )).scalar_one_or_none()
        if not existing:
            existing = models.InvoiceParty(invoice_id=invoice.id, party_type="supplier")
            db.add(existing)
        existing.name = sup_name
        existing.vat_number = normalization.normalize_vat(val("supplier_vat_number")) or existing.vat_number

    for name in ("invoice_number", "invoice_date", "due_date", "currency",
                 "subtotal_amount", "tax_amount", "total_amount", "supplier_name",
                 "supplier_vat_number", "iban"):
        v = result_fields.get(name)
        if v is None:
            continue
        ef = db.execute(select(models.ExtractionField).where(
            models.ExtractionField.invoice_id == invoice.id,
            models.ExtractionField.field_name == name,
        )).scalar_one_or_none()
        if not ef:
            ef = models.ExtractionField(invoice_id=invoice.id, field_name=name)
            db.add(ef)
        ef.raw_value = getattr(v, "value", None)
        ef.confidence = getattr(v, "confidence", None)
        ef.page_number = getattr(v, "page", None)

    db.query(models.ExtractionWarning).filter_by(invoice_id=invoice.id).delete()
    for w in warnings:
        db.add(models.ExtractionWarning(
            invoice_id=invoice.id, code=w.code, message=w.message, severity=w.severity,
        ))
    invoice.status = "needs_review"
    db.commit()

def update_invoice(db: Session, auth: AuthContext, invoice_id: str, payload: dict) -> dict:
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise ValidationError("Invoice not found")
    _, member = _require_member(db, auth, str(invoice.organization_id))
    if member.role not in ROLES_CAN_EDIT:
        raise AuthorizationError("Your role cannot edit invoices")

    if payload.get("invoice_number") is not None:
        invoice.invoice_number = payload["invoice_number"]
    if payload.get("invoice_date") is not None:
        invoice.invoice_date = payload["invoice_date"]
    if payload.get("due_date") is not None:
        invoice.due_date = payload["due_date"]
    if payload.get("currency") is not None:
        invoice.currency = payload["currency"]
    for k in ("subtotal_amount", "tax_amount", "total_amount"):
        if payload.get(k) is not None:
            setattr(invoice, k, payload[k])
    if payload.get("iban") is not None:
        invoice.iban = payload["iban"]
    if payload.get("payment_terms") is not None:
        invoice.payment_terms = payload["payment_terms"]

    sup = payload.get("supplier")
    if sup:
        party = db.execute(select(models.InvoiceParty).where(
            models.InvoiceParty.invoice_id == invoice.id,
            models.InvoiceParty.party_type == "supplier",
        )).scalar_one_or_none()
        if not party:
            party = models.InvoiceParty(invoice_id=invoice.id, party_type="supplier")
            db.add(party)
        if sup.get("name") is not None:
            party.name = sup["name"]
        if sup.get("vat_number") is not None:
            party.vat_number = sup["vat_number"]

    _recompute_warnings(db, invoice)
    db.commit()
    return get_invoice_detail(db, auth, invoice_id, _dummy_storage())


def _recompute_warnings(db: Session, invoice: models.Invoice) -> None:
    fields = {
        "supplier_name": _supplier_name(db, invoice),
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "currency": invoice.currency,
        "subtotal_amount": float(invoice.subtotal_amount) if invoice.subtotal_amount is not None else None,
        "tax_amount": float(invoice.tax_amount) if invoice.tax_amount is not None else None,
        "total_amount": float(invoice.total_amount) if invoice.total_amount is not None else None,
        "supplier_vat_number": _supplier_vat(db, invoice),
    }
    warnings = validation.generate_warnings(fields)
    db.query(models.ExtractionWarning).filter_by(invoice_id=invoice.id).delete()
    for w in warnings:
        db.add(models.ExtractionWarning(invoice_id=invoice.id, code=w.code, message=w.message, severity=w.severity))


def _supplier_name(db, invoice):
    p = db.execute(select(models.InvoiceParty).where(
        models.InvoiceParty.invoice_id == invoice.id,
        models.InvoiceParty.party_type == "supplier",
    )).scalar_one_or_none()
    return p.name if p else None


def _supplier_vat(db, invoice):
    p = db.execute(select(models.InvoiceParty).where(
        models.InvoiceParty.invoice_id == invoice.id,
        models.InvoiceParty.party_type == "supplier",
    )).scalar_one_or_none()
    return p.vat_number if p else None


def _dummy_storage():
    class _S:
        def signed_url(self, *a, **k): return ""
    return _S()


REQUIRED_FOR_APPROVAL = ("invoice_number", "invoice_date", "currency", "total_amount")


def approve_invoice(db: Session, auth: AuthContext, invoice_id: str) -> models.Invoice:
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise ValidationError("Invoice not found")
    _, member = _require_member(db, auth, str(invoice.organization_id))
    if member.role not in ROLES_CAN_APPROVE:
        raise AuthorizationError("Your role cannot approve invoices")
    if invoice.status != "needs_review":
        raise ValidationError("Only invoices needing review can be approved")
    missing = [f for f in REQUIRED_FOR_APPROVAL if not getattr(invoice, f) and f != "supplier_name"]
    sup = _supplier_name(db, invoice)
    if not sup:
        missing.append("supplier_name")
    if missing:
        raise ValidationError("Missing required fields: " + ", ".join(missing))
    errors = db.execute(select(models.ExtractionWarning).where(
        models.ExtractionWarning.invoice_id == invoice.id,
        models.ExtractionWarning.severity == "error",
    )).scalars().all()
    if errors:
        raise ValidationError("Cannot approve: error-level warnings present")
    invoice.status = "approved"
    invoice.reviewed_by_user_id = uuid.UUID(auth.user_id)
    invoice.reviewed_at = datetime.utcnow()
    db.add(models.AuditLog(
        organization_id=invoice.organization_id, actor_user_id=uuid.UUID(auth.user_id),
        action="invoice.approved", target_type="invoice", target_id=invoice.id,
    ))
    db.commit()
    return invoice


def archive_invoice(db: Session, auth: AuthContext, invoice_id: str) -> models.Invoice:
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise ValidationError("Invoice not found")
    _, member = _require_member(db, auth, str(invoice.organization_id))
    if member.role not in ROLES_CAN_EDIT:
        raise AuthorizationError("Your role cannot archive invoices")
    invoice.status = "archived"
    db.add(models.AuditLog(
        organization_id=invoice.organization_id, actor_user_id=uuid.UUID(auth.user_id),
        action="invoice.archived", target_type="invoice", target_id=invoice.id,
    ))
    db.commit()
    return invoice


def delete_invoice(db: Session, auth: AuthContext, invoice_id: str, storage: StorageBackend) -> None:
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise ValidationError("Invoice not found")
    _, member = _require_member(db, auth, str(invoice.organization_id))
    if member.role != "owner":
        raise AuthorizationError("Only owners can hard-delete invoices")
    org_id = invoice.organization_id
    storage.delete(settings.supabase_storage_originals_bucket, invoice.storage_key)
    db.delete(invoice)
    db.add(models.AuditLog(
        organization_id=org_id, actor_user_id=uuid.UUID(auth.user_id),
        action="invoice.deleted", target_type="invoice", target_id=invoice.id,
    ))
    db.commit()


def reprocess_invoice(db: Session, auth: AuthContext, invoice_id: str) -> models.Invoice:
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise ValidationError("Invoice not found")
    _, member = _require_member(db, auth, str(invoice.organization_id))
    if member.role not in ROLES_CAN_UPLOAD:
        raise AuthorizationError("Your role cannot reprocess invoices")
    invoice.status = "processing"
    job = models.ExtractionJob(invoice_id=invoice.id, status="queued",
                               provider=settings.extraction_provider, queued_at=datetime.utcnow())
    db.add(job)
    db.commit()
    _enqueue_job(invoice.id, job.id)
    return invoice
