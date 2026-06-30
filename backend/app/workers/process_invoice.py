"""Background worker that processes one extraction job (§4 flow steps 6-11)."""
from __future__ import annotations

import datetime as _dt
import logging
import os
import tempfile
import uuid

from sqlalchemy import select

from app.db.models import ExtractionJob, Invoice
from app.db.session import SessionLocal
from app.extraction.base import ExtractionResult
from app.invoices import service, validation

logger = logging.getLogger(__name__)

# Build a provider via lazily-loaded factory to avoid import cycles.
def _provider():
    from app.extraction.external_provider import get_provider
    return get_provider()


def process_invoice_job(invoice_id: str, job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ExtractionJob, uuid.UUID(job_id))
        invoice = db.get(Invoice, uuid.UUID(invoice_id))
        if not invoice or not job:
            return
        job.status = "running"
        job.started_at = _dt.datetime.utcnow()
        db.commit()

        try:
            # download file bytes from storage
            from app.storage.supabase_storage import get_storage
        except Exception:
            from app.storage.local import LocalStorage
            def get_storage():
                from app.core.config import settings
                return LocalStorage(settings.local_storage_dir)
        storage = get_storage()

        suffix = ".pdf" if "pdf" in invoice.file_mime_type else ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(storage.get(
                __import__("app.core.config", fromlist=["settings"]).settings.supabase_storage_originals_bucket,
                invoice.storage_key,
            ))
            file_path = tmp.name

        try:
            result: ExtractionResult = _provider().extract(file_path, invoice.file_mime_type)
        finally:
            os.unlink(file_path)

        fields_with_raw = {k: v for k, v in result.fields.items()}
        fields_with_raw["__raw_text__"] = result.raw_text

        confidence = validation.compute_overall_confidence(
            {k: getattr(v, "confidence", 0.0) for k, v in result.fields.items()}
        )

        # build a plain dict of normalized scalar values for validation warnings
        val_map = {}
        from app.invoices import normalization as norm

        def v(name):
            node = result.fields.get(name)
            return getattr(node, "value", None) if node else None

        val_map["invoice_number"] = v("invoice_number")
        val_map["invoice_date"] = norm.normalize_date(v("invoice_date"))
        val_map["due_date"] = norm.normalize_date(v("due_date"))
        val_map["currency"] = norm.normalize_currency(v("currency"))
        val_map["subtotal_amount"] = norm.normalize_amount(v("subtotal_amount"))
        val_map["tax_amount"] = norm.normalize_amount(v("tax_amount"))
        val_map["total_amount"] = norm.normalize_amount(v("total_amount"))
        val_map["supplier_name"] = norm.normalize_supplier_name(v("supplier_name"))
        val_map["supplier_vat_number"] = norm.normalize_vat(v("supplier_vat_number"))
        val_map["iban"] = v("iban")

        warnings = validation.generate_warnings(val_map)
        if not result.line_items:
            warnings.append(validation.Warning("line_items_not_extracted",
                                               "Line items were not extracted for this invoice.",
                                               "info"))

        job.status = "succeeded"
        job.finished_at = _dt.datetime.utcnow()
        db.commit()

        service.apply_extraction_result(db, invoice_id, fields_with_raw, confidence, warnings)
    except Exception as exc:
        logger.exception("Extraction failed for invoice %s", invoice_id)
        job = db.get(ExtractionJob, uuid.UUID(job_id))
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = _dt.datetime.utcnow()
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        if inv:
            inv.status = "failed"
        db.commit()
    finally:
        db.close()