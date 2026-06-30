"""SQLAlchemy ORM models mirroring the schema in INVOICE_SAAS_PLANNING.md §6."""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, BigInteger, Numeric, Date, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CreatedAtMixin:
    """For append-only tables (usage_events, audit_logs) that have no updated_at (§6)."""
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    auth_provider: Mapped[Optional[str]] = mapped_column(Text)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    billing_email: Mapped[Optional[str]] = mapped_column(Text)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(Text)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(Text)
    subscription_status: Mapped[str] = mapped_column(Text, nullable=False, default="free")
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="free")
    usage_period_start: Mapped[Optional[date]] = mapped_column(Date)
    usage_period_end: Mapped[Optional[date]] = mapped_column(Date)


class OrganizationMember(TimestampMixin, Base):
    __tablename__ = "organization_members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[Optional[str]] = mapped_column(Text)
    vat_number: Mapped[Optional[str]] = mapped_column(Text)
    tax_id: Mapped[Optional[str]] = mapped_column(Text)
    iban: Mapped[Optional[str]] = mapped_column(Text)
    default_expense_category: Mapped[Optional[str]] = mapped_column(Text)


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    document_hash: Mapped[Optional[str]] = mapped_column(Text)
    duplicate_of_invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    invoice_number: Mapped[Optional[str]] = mapped_column(Text)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    currency: Mapped[Optional[str]] = mapped_column(Text)
    subtotal_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    iban: Mapped[Optional[str]] = mapped_column(Text)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class InvoiceParty(TimestampMixin, Base):
    __tablename__ = "invoice_parties"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    party_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text)
    vat_number: Mapped[Optional[str]] = mapped_column(Text)
    tax_id: Mapped[Optional[str]] = mapped_column(Text)
    address_line1: Mapped[Optional[str]] = mapped_column(Text)
    address_line2: Mapped[Optional[str]] = mapped_column(Text)
    postal_code: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(Text)
    country_code: Mapped[Optional[str]] = mapped_column(Text)


class InvoiceLineItem(TimestampMixin, Base):
    __tablename__ = "invoice_line_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    line_number: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    tax_rate: Mapped[Optional[float]] = mapped_column(Numeric(7, 4))
    tax_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))


class InvoiceTaxBreakdown(TimestampMixin, Base):
    __tablename__ = "invoice_tax_breakdowns"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    tax_rate: Mapped[Optional[float]] = mapped_column(Numeric(7, 4))
    taxable_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    label: Mapped[Optional[str]] = mapped_column(Text)


class ExtractionField(TimestampMixin, Base):
    __tablename__ = "extraction_fields"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[Optional[str]] = mapped_column(Text)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    source: Mapped[Optional[str]] = mapped_column(Text)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    bbox_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("invoice_id", "field_name", name="uq_invoice_field"),)


class ExtractionWarning(TimestampMixin, Base):
    __tablename__ = "extraction_warnings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)


class ExtractionJob(TimestampMixin, Base):
    __tablename__ = "extraction_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    queued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    raw_result_storage_key: Mapped[Optional[str]] = mapped_column(Text)


class ExportJob(TimestampMixin, Base):
    __tablename__ = "export_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    filter_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    storage_key: Mapped[Optional[str]] = mapped_column(Text)
    row_count: Mapped[Optional[int]] = mapped_column(Integer)


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class UsageEvent(CreatedAtMixin, Base):
    __tablename__ = "usage_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(Text)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)