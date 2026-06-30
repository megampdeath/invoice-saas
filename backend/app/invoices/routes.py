"""Invoice API routes (§7). All endpoints require Supabase auth + org membership."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import AuthContext, get_current_user
from app.core.config import settings
from app.db import models, session
from app.invoices import exports, schemas, service
from app.storage.supabase_storage import get_storage

router = APIRouter(prefix="/api", tags=["invoices"])


def _storage():
    try:
        return get_storage()
    except Exception:
        from app.storage.local import LocalStorage
        from app.core.config import settings
        return LocalStorage(settings.local_storage_dir)


@router.get("/health")
def health():
    return {"status": "ok", "app_env": __import__("app.core.config", fromlist=["settings"]).settings.app_env}


@router.get("/me")
def me(auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    user = service.ensure_user_profile(db, auth)
    # Free onboarding: ensure the user has a workspace to work in.
    service.ensure_default_organization(db, auth)
    rows = db.execute(
        select(models.Organization, models.OrganizationMember.role)
        .join(models.OrganizationMember, models.OrganizationMember.organization_id == models.Organization.id)
        .where(models.OrganizationMember.user_id == user.id)
    ).all()
    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "organizations": [
            {"id": str(org.id), "name": org.name, "slug": org.slug, "plan": org.plan, "role": role}
            for org, role in rows
        ],
    }


@router.post("/invoices", response_model=schemas.InvoiceUploadResponse, status_code=201)
def upload_invoice(
    organization_id: str = Form(...),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(session.get_db),
):
    data = file.file.read()
    try:
        inv = service.upload_invoice(db, auth, organization_id, file.filename, file.content_type, data, _storage())
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"id": str(inv.id), "status": inv.status, "original_filename": inv.original_filename}


@router.get("/invoices", response_model=schemas.InvoiceList)
def list_invoices(
    organization_id: str = Query(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(session.get_db),
):
    try:
        res = service.list_invoices(db, auth, organization_id, status_filter, search, page, page_size)
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    items = [schemas.InvoiceListItem(
        id=str(i.id), status=i.status, original_filename=i.original_filename,
        invoice_number=i.invoice_number, invoice_date=i.invoice_date,
        total_amount=i.total_amount, currency=i.currency, created_at=i.created_at,
    ) for i in res["items"]]
    return {"items": items, "page": res["page"], "page_size": res["page_size"], "total": res["total"]}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    try:
        return service.get_invoice_detail(db, auth, invoice_id, _storage())
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/invoices/{invoice_id}/file")
def get_invoice_file(invoice_id: str, exp: int = Query(...), sig: str = Query(...),
                     download: int = Query(0), db: Session = Depends(session.get_db)):
    """Serve the original invoice file for in-browser preview (inline) or download.

    Auth model: iframes/<img> tags cannot send a Bearer header, so this endpoint
    authenticates via a short-lived HMAC token (exp+sig) tied to this invoice_id
    and signed with PREVIEW_TOKEN_SECRET. The token is only ever minted by
    `get_invoice_detail` (which already checks Supabase JWT + org membership),
    so possession of a valid, unexpired token proves the caller was authorized
    to view this invoice. The token expires in 10 minutes.
    """
    if not service.verify_file_token(invoice_id, exp, sig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid or expired file link")
    invoice = db.get(models.Invoice, uuid.UUID(invoice_id))
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    storage = _storage()
    data = storage.get(settings.supabase_storage_originals_bucket, invoice.storage_key)
    disposition = "attachment" if download else "inline"
    from urllib.parse import quote
    fname = quote(invoice.original_filename)
    headers = {
        "Content-Type": invoice.file_mime_type or "application/octet-stream",
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{fname}",
        "Cache-Control": "private, max-age=600",
    }
    return Response(content=data, headers=headers, media_type=invoice.file_mime_type or "application/octet-stream")


@router.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: str, payload: schemas.InvoiceUpdate,
                   auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    try:
        return service.update_invoice(db, auth, invoice_id, payload.model_dump(exclude_unset=True))
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    try:
        inv = service.approve_invoice(db, auth, invoice_id)
        return {"id": str(inv.id), "status": inv.status}
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/invoices/{invoice_id}/reprocess")
def reprocess(invoice_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    try:
        inv = service.reprocess_invoice(db, auth, invoice_id)
        return {"id": str(inv.id), "status": inv.status}
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/invoices/{invoice_id}/archive")
def archive(invoice_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    try:
        inv = service.archive_invoice(db, auth, invoice_id)
        return {"id": str(inv.id), "status": inv.status}
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    try:
        service.delete_invoice(db, auth, invoice_id, _storage())
    except service.AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except service.ValidationError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/exports", response_model=schemas.ExportJobOut, status_code=201)
def create_export(req: schemas.ExportRequest, auth: AuthContext = Depends(get_current_user),
                  db: Session = Depends(session.get_db)):
    _, _ = service._require_member(db, auth, req.organization_id)  # authz
    job = models.ExportJob(
        organization_id=uuid.UUID(req.organization_id),
        created_by_user_id=uuid.UUID(auth.user_id),
        status="queued", format=req.format,
        filter_json={"status": req.status, "from": str(req.frm) if req.frm else None, "to": str(req.to) if req.to else None},
    )
    db.add(job)
    db.commit()
    # Enqueue, with inline fallback when Redis is unavailable (dev).
    if __import__("app.core.config", fromlist=["settings"]).settings.redis_url:
        try:
            from redis import Redis
            from rq import Queue
            from app.core.config import settings
            Queue("exports", connection=Redis.from_url(settings.redis_url)).enqueue(exports.run_export_job, str(job.id))
        except Exception:
            exports.run_export_job(str(job.id))
    else:
        exports.run_export_job(str(job.id))
    return {"export_job_id": str(job.id), "status": job.status}


@router.get("/exports")
def list_exports(organization_id: str = Query(...), auth: AuthContext = Depends(get_current_user),
                 db: Session = Depends(session.get_db)):
    service._require_member(db, auth, organization_id)
    rows = db.execute(
        __import__("sqlalchemy").select(models.ExportJob)
        .where(models.ExportJob.organization_id == uuid.UUID(organization_id))
        .order_by(models.ExportJob.created_at.desc())
    ).scalars().all()
    out = []
    from app.core.config import settings as _s
    for j in rows:
        url = ""
        if j.storage_key and j.status == "succeeded":
            try:
                url = _storage().signed_url(_s.supabase_storage_exports_bucket, j.storage_key, 600)
            except Exception:
                url = ""
        out.append({"id": str(j.id), "status": j.status, "format": j.format,
                    "row_count": j.row_count, "download_url": url})
    return out


@router.get("/exports/{export_job_id}", response_model=schemas.ExportStatusOut)
def export_status(export_job_id: str, auth: AuthContext = Depends(get_current_user), db: Session = Depends(session.get_db)):
    job = db.get(models.ExportJob, uuid.UUID(export_job_id))
    if not job:
        raise HTTPException(404, "Export job not found")
    service._require_member(db, auth, str(job.organization_id))
    from app.core.config import settings
    url = ""
    if job.storage_key and job.status == "succeeded":
        try:
            url = _storage().signed_url(settings.supabase_storage_exports_bucket, job.storage_key, 600)
        except Exception:
            url = ""
    return {"id": str(job.id), "status": job.status, "format": job.format,
            "row_count": job.row_count, "download_url": url}