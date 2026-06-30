"""External OCR provider adapter.

Default production adapter: AWS Textract AnalyzeExpense (§11). Credentials come
from environment variables (AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).
Falls back gracefully when boto3/credentials are unavailable.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.extraction.base import ExtractionResult, FieldResult, InvoiceExtractionProvider

logger = logging.getLogger(__name__)


class AwsTextractExpenseProvider(InvoiceExtractionProvider):
    name = "textract"

    def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        try:
            import boto3
        except Exception:  # pragma: no cover - dependency optional in dev
            logger.error("boto3 not installed; cannot run Textract")
            return ExtractionResult(provider=self.name)

        if not (settings.aws_access_key_id and settings.aws_secret_access_key and settings.aws_region):
            logger.error("AWS credentials not configured for Textract")
            return ExtractionResult(provider=self.name)

        client = boto3.client(
            "textract",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        with open(file_path, "rb") as fh:
            payload = fh.read()

        try:
            resp = client.analyze_expense(Document={"Bytes": payload})
        except Exception as exc:  # pragma: no cover - network
            logger.error("Textract call failed: %s", exc)
            return ExtractionResult(provider=self.name)

        fields: dict[str, FieldResult] = {}
        for doc in resp.get("ExpenseDocuments", []):
            for group in doc.get("SummaryFields", []):
                label = group.get("Type", {}).get("Text")
                val_node = group.get("ValueDetection")
                val = val_node.get("Text") if val_node else None
                conf = (val_node.get("Confidence") / 100.0) if val_node else 0.0
                key = {
                    "INVOICE_RECEIPT_ID": "invoice_number",
                    "TOTAL": "total_amount",
                    "SUBTOTAL": "subtotal_amount",
                    "TAX": "tax_amount",
                    "VENDOR_NAME": "supplier_name",
                    "DUE_DATE": "due_date",
                    "INVOICE_RECEIPT_DATE": "invoice_date",
                    "CURRENCY": "currency",
                }.get(label or "")
                if key and val:
                    fields.setdefault(key, FieldResult(val, round(conf, 4), 1))
        return ExtractionResult(fields=fields, provider=self.name)


def get_provider(name: Optional[str] = None) -> InvoiceExtractionProvider:
    name = (name or settings.extraction_provider or "mock").lower()
    mapping = {
        "mock": MockExtractionProvider,
        "pdf_text": TextPdfExtractionProvider,
        "textract": AwsTextractExpenseProvider,
    }
    cls = mapping.get(name, MockExtractionProvider)
    return cls()


# Late imports to avoid cycles.
from app.extraction.mock_provider import MockExtractionProvider  # noqa: E402
from app.extraction.pdf_text_provider import TextPdfExtractionProvider  # noqa: E402