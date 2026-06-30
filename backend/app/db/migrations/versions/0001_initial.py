"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('create extension if not exists "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text),
        sa.Column("avatar_url", sa.Text),
        sa.Column("auth_provider", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.execute(
        """
        create or replace function public.handle_new_user()
        returns trigger as $$
        begin
          insert into public.users (id, email)
          values (new.id, new.email)
          on conflict (id) do nothing;
          return new;
        end;
        $$ language plpgsql security definer;

        create trigger on_auth_user_created
        after insert on auth.users
        for each row execute function public.handle_new_user();
        """
    )

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("billing_email", sa.Text),
        sa.Column("stripe_customer_id", sa.Text),
        sa.Column("stripe_subscription_id", sa.Text),
        sa.Column("subscription_status", sa.Text, nullable=False, server_default="free"),
        sa.Column("plan", sa.Text, nullable=False, server_default="free"),
        sa.Column("usage_period_start", sa.Date),
        sa.Column("usage_period_end", sa.Date),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("normalized_name", sa.Text),
        sa.Column("vat_number", sa.Text),
        sa.Column("tax_id", sa.Text),
        sa.Column("iban", sa.Text),
        sa.Column("default_expense_category", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("original_filename", sa.Text, nullable=False),
        sa.Column("file_mime_type", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("page_count", sa.Integer),
        sa.Column("document_hash", sa.Text),
        sa.Column("duplicate_of_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id")),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("invoice_number", sa.Text),
        sa.Column("invoice_date", sa.Date),
        sa.Column("due_date", sa.Date),
        sa.Column("currency", sa.Text),
        sa.Column("subtotal_amount", sa.Numeric(14, 2)),
        sa.Column("tax_amount", sa.Numeric(14, 2)),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column("iban", sa.Text),
        sa.Column("payment_terms", sa.Text),
        sa.Column("raw_text", sa.Text),
        sa.Column("extraction_confidence", sa.Numeric(5, 4)),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "invoice_parties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("party_type", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("vat_number", sa.Text),
        sa.Column("tax_id", sa.Text),
        sa.Column("address_line1", sa.Text),
        sa.Column("address_line2", sa.Text),
        sa.Column("postal_code", sa.Text),
        sa.Column("city", sa.Text),
        sa.Column("country_code", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "invoice_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("line_number", sa.Integer),
        sa.Column("description", sa.Text),
        sa.Column("quantity", sa.Numeric(14, 4)),
        sa.Column("unit_price", sa.Numeric(14, 4)),
        sa.Column("tax_rate", sa.Numeric(7, 4)),
        sa.Column("tax_amount", sa.Numeric(14, 2)),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "invoice_tax_breakdowns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("tax_rate", sa.Numeric(7, 4)),
        sa.Column("taxable_amount", sa.Numeric(14, 2)),
        sa.Column("tax_amount", sa.Numeric(14, 2)),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column("label", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "extraction_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("field_name", sa.Text, nullable=False),
        sa.Column("raw_value", sa.Text),
        sa.Column("normalized_value", sa.Text),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("source", sa.Text),
        sa.Column("page_number", sa.Integer),
        sa.Column("bbox_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("invoice_id", "field_name", name="uq_invoice_field"),
    )

    op.create_table(
        "extraction_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "extraction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("queued_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("error_code", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("raw_result_storage_key", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("format", sa.Text, nullable=False),
        sa.Column("filter_json", postgresql.JSONB),
        sa.Column("storage_key", sa.Text),
        sa.Column("row_count", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("key_prefix", sa.Text, nullable=False),
        sa.Column("key_hash", sa.Text, nullable=False),
        sa.Column("last_used_at", sa.DateTime),
        sa.Column("revoked_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("metadata_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # add updated_at triggers
    op.execute(
        """
        create or replace function public.touch_updated_at()
        returns trigger as $$
        begin
          new.updated_at = now();
          return new;
        end;
        $$ language plpgsql;
        """
    )
    for tbl in (
        "users", "organizations", "organization_members", "suppliers", "invoices",
        "invoice_parties", "invoice_line_items", "invoice_tax_breakdowns",
        "extraction_fields", "extraction_warnings", "extraction_jobs", "export_jobs",
        "api_keys", "usage_events",
    ):
        op.execute(
            f"create trigger trg_touch_{tbl} before update on public.{tbl} "
            f"for each row execute function public.touch_updated_at();"
        )


def downgrade() -> None:
    for tbl in (
        "audit_logs", "usage_events", "api_keys", "export_jobs", "extraction_jobs",
        "extraction_warnings", "extraction_fields", "invoice_tax_breakdowns",
        "invoice_line_items", "invoice_parties", "invoices", "suppliers",
        "organization_members", "organizations", "users",
    ):
        op.drop_table(tbl)
    op.execute("drop trigger if exists on_auth_user_created on auth.users;")
    op.execute("drop function if exists public.handle_new_user();")
    op.execute("drop function if exists public.touch_updated_at();")