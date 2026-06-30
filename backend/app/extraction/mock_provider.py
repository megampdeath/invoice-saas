"""Deterministic mock provider for local dev and tests."""
from __future__ import annotations

from app.extraction.base import ExtractionResult, FieldResult, InvoiceExtractionProvider


class MockExtractionProvider(InvoiceExtractionProvider):
    name = "mock"

    def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        return ExtractionResult(
            raw_text="Mock invoice body",
            fields={
                "invoice_number": FieldResult("FA-2026-001", 0.92, 1),
                "invoice_date": FieldResult("2026-06-23", 0.88, 1),
                "due_date": FieldResult("2026-07-23", 0.80, 1),
                "currency": FieldResult("EUR", 0.99, 1),
                "subtotal_amount": FieldResult("1000.00", 0.90, 1),
                "tax_amount": FieldResult("200.00", 0.85, 1),
                "total_amount": FieldResult("1200.00", 0.98, 1),
                "supplier_name": FieldResult("Example SARL", 0.93, 1),
                "supplier_vat_number": FieldResult("FR12345678901", 0.70, 1),
                "iban": FieldResult("FR7630006000011234567890189", 0.60, 1),
            },
            provider=self.name,
        )