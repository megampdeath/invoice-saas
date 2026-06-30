"""Pydantic schemas for invoice endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InvoiceUploadResponse(BaseModel):
    id: str
    status: str
    original_filename: str


class SupplierIn(BaseModel):
    name: Optional[str] = None
    vat_number: Optional[str] = None


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    subtotal_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    iban: Optional[str] = None
    payment_terms: Optional[str] = None
    supplier: Optional[SupplierIn] = None


class InvoiceWarningOut(BaseModel):
    code: str
    message: str
    severity: str


class InvoiceDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    original_filename: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    subtotal_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    iban: Optional[str] = None
    payment_terms: Optional[str] = None
    supplier: Optional[SupplierIn] = None
    confidence: float = 0.0
    warnings: list[InvoiceWarningOut] = []
    file_preview_url: Optional[str] = None


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    original_filename: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    created_at: datetime


class InvoiceList(BaseModel):
    items: list[InvoiceListItem]
    page: int
    page_size: int
    total: int


class ExportRequest(BaseModel):
    organization_id: str
    format: str  # csv | xlsx
    status: Optional[str] = "approved"
    frm: Optional[date] = None
    to: Optional[date] = None


class ExportJobOut(BaseModel):
    export_job_id: str
    status: str


class ExportStatusOut(BaseModel):
    id: str
    status: str
    format: str
    row_count: Optional[int]
    download_url: Optional[str] = None