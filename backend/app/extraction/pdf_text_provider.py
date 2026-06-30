"""Digital PDF text extraction + rule-based parser (§11, Milestone 5)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.extraction.base import ExtractionResult, FieldResult, InvoiceExtractionProvider


def _extract_text_from_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(file_path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


_DATE_PATTERNS = [
    r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b",
    r"\b(\d{4}-\d{2}-\d{2})\b",
]


def _find_date(text: str, label_regex: str) -> Optional[str]:
    m = re.search(label_regex, text, re.IGNORECASE)
    if not m:
        return None
    after = text[m.end(): m.end() + 40]
    for pat in _DATE_PATTERNS:
        dm = re.search(pat, after)
        if dm:
            return dm.group(1)
    return None


def _parse_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


_AMOUNT_RE = re.compile(r"(\d[\d\s.,]*\d|\d)")


def _find_amount(text: str, label_regex: str) -> Optional[str]:
    m = re.search(label_regex, text, re.IGNORECASE)
    if not m:
        return None
    after = text[m.end(): m.end() + 60]
    am = re.search(r"(\d[\d\s.,]*\d)", after)
    return am.group(1) if am else None


class TextPdfExtractionProvider(InvoiceExtractionProvider):
    name = "pdf_text"

    def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        raw = _extract_text_from_pdf(file_path)
        fields: dict[str, FieldResult] = {}

        inv = re.search(r"(?:invoice|facture)\s*(?:no\.?|n°|#|num(?:ber)?)[\s:]*([A-Za-z0-9\-/]+)", raw, re.IGNORECASE)
        if inv:
            fields["invoice_number"] = FieldResult(inv.group(1), 0.7, 1)

        d = _parse_date(_find_date(raw, r"(invoice|facture)\s*(date)"))
        if d:
            fields["invoice_date"] = FieldResult(d, 0.6, 1)
        d = _parse_date(_find_date(raw, r"(due|échéance)\s*(date)"))
        if d:
            fields["due_date"] = FieldResult(d, 0.6, 1)

        for label, fname in ((r"(total)\s*( TTC| ht)?", "total_amount"),
                             (r"(subtotal|net|sous-total|montant ht)", "subtotal_amount"),
                             (r"(tax|tva|vat)", "tax_amount")):
            amt = _find_amount(raw, label)
            if amt:
                fields[fname] = FieldResult(amt, 0.6, 1)

        cur = re.search(r"\b(EUR|USD|GBP|MAD)\b|\b(€|\$|£)\b", raw)
        if cur:
            val = cur.group(1) or {"€": "EUR", "$": "USD", "£": "GBP"}[cur.group(2)]
            fields["currency"] = FieldResult(val, 0.95, 1)

        return ExtractionResult(raw_text=raw, fields=fields, provider=self.name)