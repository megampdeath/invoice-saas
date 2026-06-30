"""Validation logic producing warnings (§12). Pure functions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


TOLERANCE = 0.02


@dataclass
class Warning:
    code: str
    message: str
    severity: str  # info | warning | error


def check_required_fields(fields: dict) -> list[Warning]:
    out: list[Warning] = []
    required = {
        "supplier_name": "Supplier name",
        "invoice_number": "Invoice number",
        "invoice_date": "Invoice date",
        "total_amount": "Total amount",
        "currency": "Currency",
    }
    for key, label in required.items():
        if not fields.get(key):
            out.append(Warning("missing_" + key, f"{label} is missing", "warning"))
    return out


def check_amounts(fields: dict) -> list[Warning]:
    out: list[Warning] = []
    subtotal = fields.get("subtotal_amount")
    tax = fields.get("tax_amount")
    total = fields.get("total_amount")
    if subtotal is not None and tax is not None and total is not None:
        if abs((subtotal + tax) - total) > TOLERANCE:
            out.append(Warning(
                "subtotal_tax_total_mismatch",
                f"Subtotal + tax ({subtotal + tax:.2f}) does not equal total ({total:.2f}).",
                "error",
            ))
    return out


def check_dates(fields: dict) -> list[Warning]:
    out: list[Warning] = []
    inv = fields.get("invoice_date")
    due = fields.get("due_date")
    if inv and due and due < inv:
        out.append(Warning("due_before_invoice", "Due date is before invoice date.", "warning"))
    if inv:
        today = date.today()
        if isinstance(inv, date):
            if inv.year < 2000 or inv.year > today.year + 1:
                out.append(Warning("implausible_invoice_date", "Invoice date is implausibly old or in the future.", "warning"))
    return out


def check_vat_format(fields: dict) -> list[Warning]:
    out: list[Warning] = []
    vat = fields.get("supplier_vat_number")
    if vat:
        import re
        if not re.match(r"^[A-Z]{2}[A-Z0-9]{2,}$", str(vat)) and not re.match(r"^[A-Z0-9]{6,}$", str(vat)):
            out.append(Warning("invalid_vat_format", f"VAT number '{vat}' looks malformed.", "warning"))
    return out


def generate_warnings(fields: dict) -> list[Warning]:
    warnings: list[Warning] = []
    warnings += check_required_fields(fields)
    warnings += check_amounts(fields)
    warnings += check_dates(fields)
    warnings += check_vat_format(fields)
    return warnings


# Confidence weighting (§12)
CONFIDENCE_WEIGHTS = {
    "invoice_number": 0.15,
    "supplier_name": 0.20,
    "invoice_date": 0.15,
    "total_amount": 0.25,
    "tax_amount": 0.10,
    "subtotal_amount": 0.10,
    "currency": 0.05,
}


def compute_overall_confidence(per_field: dict[str, float]) -> float:
    total = 0.0
    weight_sum = 0.0
    for key, w in CONFIDENCE_WEIGHTS.items():
        if key in per_field:
            total += per_field[key] * w
            weight_sum += w
    return round(total / weight_sum, 4) if weight_sum else 0.0


def detect_duplicates(org_invoice_rows: list[dict], new_invoice: dict) -> Optional[str]:
    """Return a duplicate warning code if any matching row exists."""
    for row in org_invoice_rows:
        if row.get("id") == new_invoice.get("id"):
            continue
        same_supplier = row.get("supplier_name") == new_invoice.get("supplier_name")
        same_number = row.get("invoice_number") == new_invoice.get("invoice_number")
        if same_supplier and same_number and new_invoice.get("invoice_number"):
            return "duplicate_invoice_detected"
        if row.get("document_hash") and row.get("document_hash") == new_invoice.get("document_hash"):
            return "duplicate_invoice_detected"
        if (same_supplier and row.get("total_amount") == new_invoice.get("total_amount")
                and row.get("invoice_date") == new_invoice.get("invoice_date") and new_invoice.get("total_amount")):
            return "duplicate_invoice_detected"
    return None