"""CSV/XLSX export generation (§13)."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from app.db.models import ExportJob, ExtractionWarning, Invoice, InvoiceParty
from app.db.session import SessionLocal


EXPORT_COLUMNS = [
    "invoice_id", "status", "supplier_name", "supplier_vat_number", "invoice_number",
    "invoice_date", "due_date", "currency", "subtotal_amount", "tax_amount", "total_amount",
    "iban", "payment_terms", "original_filename", "uploaded_at", "reviewed_at", "warnings",
]


def _row_from_invoice(db, inv: Invoice) -> dict:
    party = db.execute(select(InvoiceParty).where(
        InvoiceParty.invoice_id == inv.id, InvoiceParty.party_type == "supplier",
    )).scalar_one_or_none()
    warnings = db.execute(select(ExtractionWarning).where(ExtractionWarning.invoice_id == inv.id)).scalars().all()
    warn_codes = ";".join(w.code for w in warnings)
    return {
        "invoice_id": str(inv.id),
        "status": inv.status,
        "supplier_name": party.name if party else "",
        "supplier_vat_number": party.vat_number if party else "",
        "invoice_number": inv.invoice_number or "",
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else "",
        "due_date": inv.due_date.isoformat() if inv.due_date else "",
        "currency": inv.currency or "",
        "subtotal_amount": f"{float(inv.subtotal_amount):.2f}" if inv.subtotal_amount is not None else "",
        "tax_amount": f"{float(inv.tax_amount):.2f}" if inv.tax_amount is not None else "",
        "total_amount": f"{float(inv.total_amount):.2f}" if inv.total_amount is not None else "",
        "iban": inv.iban or "",
        "payment_terms": inv.payment_terms or "",
        "original_filename": inv.original_filename,
        "uploaded_at": inv.created_at.isoformat() if inv.created_at else "",
        "reviewed_at": inv.reviewed_at.isoformat() if inv.reviewed_at else "",
        "warnings": warn_codes,
    }


def _select_invoices(db, org_id, status, frm, to):
    q = select(Invoice).where(Invoice.organization_id == org_id)
    if status:
        q = q.where(Invoice.status == status)
    if frm:
        q = q.where(Invoice.invoice_date >= frm)
    if to:
        q = q.where(Invoice.invoice_date <= to)
    return db.execute(q.order_by(Invoice.created_at.desc())).scalars().all()


def generate_csv(db, org_id, status, frm, to) -> tuple[bytes, int]:
    invoices = _select_invoices(db, org_id, status, frm, to)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    for inv in invoices:
        writer.writerow(_row_from_invoice(db, inv))
    return buf.getvalue().encode("utf-8"), len(invoices)


def generate_xlsx(db, org_id, status, frm, to) -> tuple[bytes, int]:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    invoices = _select_invoices(db, org_id, status, frm, to)
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.append(EXPORT_COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for inv in invoices:
        row = _row_from_invoice(db, inv)
        ws.append([row[c] for c in EXPORT_COLUMNS])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), len(invoices)


def build_filename(fmt: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"invoices-export-{stamp}.{fmt}"


def run_export_job(export_job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ExportJob, export_job_id)
        if not job:
            return
        from app.storage.supabase_storage import get_storage
        try:
            storage = get_storage()
        except Exception:
            from app.storage.local import LocalStorage
            from app.core.config import settings
            storage = LocalStorage(settings.local_storage_dir)
        job.status = "running"
        db.commit()
        flt = job.filter_json or {}
        if job.format == "csv":
            data, n = generate_csv(db, job.organization_id, flt.get("status"), flt.get("from"), flt.get("to"))
        else:
            data, n = generate_xlsx(db, job.organization_id, flt.get("status"), flt.get("from"), flt.get("to"))
        from app.core.config import settings
        key = f"{job.organization_id}/exports/{job.id}/{build_filename(job.format)}"
        storage.put(settings.supabase_storage_exports_bucket, key, data,
                    "text/csv" if job.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        job.storage_key = key
        job.row_count = n
        job.status = "succeeded"
        db.commit()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("export failed")
        job = db.get(ExportJob, export_job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
        db.commit()
    finally:
        db.close()