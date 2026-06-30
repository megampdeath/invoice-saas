-- ============================================================
-- Invoice SaaS — one-time database setup
-- Run ONCE in: Supabase Studio → SQL Editor → New query → Run
-- (The SQL Editor connects as the postgres superuser, which is the
--  only role allowed to create tables in this project.)
-- ============================================================

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

create extension if not exists "pgcrypto";

CREATE TABLE users (
    id UUID NOT NULL, 
    email TEXT NOT NULL, 
    name TEXT, 
    avatar_url TEXT, 
    auth_provider TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

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
        for each row execute function public.handle_new_user();;

CREATE TABLE organizations (
    id UUID NOT NULL, 
    name TEXT NOT NULL, 
    slug TEXT NOT NULL, 
    billing_email TEXT, 
    stripe_customer_id TEXT, 
    stripe_subscription_id TEXT, 
    subscription_status TEXT DEFAULT 'free' NOT NULL, 
    plan TEXT DEFAULT 'free' NOT NULL, 
    usage_period_start DATE, 
    usage_period_end DATE, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (slug)
);

CREATE TABLE organization_members (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_org_member UNIQUE (organization_id, user_id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE suppliers (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    name TEXT NOT NULL, 
    normalized_name TEXT, 
    vat_number TEXT, 
    tax_id TEXT, 
    iban TEXT, 
    default_expense_category TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE invoices (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    uploaded_by_user_id UUID NOT NULL, 
    status TEXT NOT NULL, 
    original_filename TEXT NOT NULL, 
    file_mime_type TEXT NOT NULL, 
    file_size_bytes BIGINT NOT NULL, 
    storage_key TEXT NOT NULL, 
    page_count INTEGER, 
    document_hash TEXT, 
    duplicate_of_invoice_id UUID, 
    supplier_id UUID, 
    invoice_number TEXT, 
    invoice_date DATE, 
    due_date DATE, 
    currency TEXT, 
    subtotal_amount NUMERIC(14, 2), 
    tax_amount NUMERIC(14, 2), 
    total_amount NUMERIC(14, 2), 
    iban TEXT, 
    payment_terms TEXT, 
    raw_text TEXT, 
    extraction_confidence NUMERIC(5, 4), 
    reviewed_by_user_id UUID, 
    reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id), 
    FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id), 
    FOREIGN KEY(duplicate_of_invoice_id) REFERENCES invoices (id), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
    FOREIGN KEY(reviewed_by_user_id) REFERENCES users (id)
);

CREATE TABLE invoice_parties (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    party_type TEXT NOT NULL, 
    name TEXT, 
    vat_number TEXT, 
    tax_id TEXT, 
    address_line1 TEXT, 
    address_line2 TEXT, 
    postal_code TEXT, 
    city TEXT, 
    country_code TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE invoice_line_items (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    line_number INTEGER, 
    description TEXT, 
    quantity NUMERIC(14, 4), 
    unit_price NUMERIC(14, 4), 
    tax_rate NUMERIC(7, 4), 
    tax_amount NUMERIC(14, 2), 
    total_amount NUMERIC(14, 2), 
    confidence NUMERIC(5, 4), 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE invoice_tax_breakdowns (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    tax_rate NUMERIC(7, 4), 
    taxable_amount NUMERIC(14, 2), 
    tax_amount NUMERIC(14, 2), 
    total_amount NUMERIC(14, 2), 
    label TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE extraction_fields (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    field_name TEXT NOT NULL, 
    raw_value TEXT, 
    normalized_value TEXT, 
    confidence NUMERIC(5, 4), 
    source TEXT, 
    page_number INTEGER, 
    bbox_json JSONB, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_invoice_field UNIQUE (invoice_id, field_name), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE extraction_warnings (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    code TEXT NOT NULL, 
    message TEXT NOT NULL, 
    severity TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE extraction_jobs (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    status TEXT NOT NULL, 
    provider TEXT NOT NULL, 
    attempt INTEGER DEFAULT '1' NOT NULL, 
    max_attempts INTEGER DEFAULT '3' NOT NULL, 
    queued_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITHOUT TIME ZONE, 
    finished_at TIMESTAMP WITHOUT TIME ZONE, 
    error_code TEXT, 
    error_message TEXT, 
    raw_result_storage_key TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE export_jobs (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    status TEXT NOT NULL, 
    format TEXT NOT NULL, 
    filter_json JSONB, 
    storage_key TEXT, 
    row_count INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id), 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);

CREATE TABLE api_keys (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    name TEXT NOT NULL, 
    key_prefix TEXT NOT NULL, 
    key_hash TEXT NOT NULL, 
    last_used_at TIMESTAMP WITHOUT TIME ZONE, 
    revoked_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE usage_events (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    event_type TEXT NOT NULL, 
    quantity INTEGER NOT NULL, 
    metadata_json JSONB, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE audit_logs (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    actor_user_id UUID, 
    action TEXT NOT NULL, 
    target_type TEXT, 
    target_id UUID, 
    metadata_json JSONB, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id), 
    FOREIGN KEY(actor_user_id) REFERENCES users (id)
);

create or replace function public.touch_updated_at()
        returns trigger as $$
        begin
          new.updated_at = now();
          return new;
        end;
        $$ language plpgsql;;

create trigger trg_touch_users before update on public.users for each row execute function public.touch_updated_at();;

create trigger trg_touch_organizations before update on public.organizations for each row execute function public.touch_updated_at();;

create trigger trg_touch_organization_members before update on public.organization_members for each row execute function public.touch_updated_at();;

create trigger trg_touch_suppliers before update on public.suppliers for each row execute function public.touch_updated_at();;

create trigger trg_touch_invoices before update on public.invoices for each row execute function public.touch_updated_at();;

create trigger trg_touch_invoice_parties before update on public.invoice_parties for each row execute function public.touch_updated_at();;

create trigger trg_touch_invoice_line_items before update on public.invoice_line_items for each row execute function public.touch_updated_at();;

create trigger trg_touch_invoice_tax_breakdowns before update on public.invoice_tax_breakdowns for each row execute function public.touch_updated_at();;

create trigger trg_touch_extraction_fields before update on public.extraction_fields for each row execute function public.touch_updated_at();;

create trigger trg_touch_extraction_warnings before update on public.extraction_warnings for each row execute function public.touch_updated_at();;

create trigger trg_touch_extraction_jobs before update on public.extraction_jobs for each row execute function public.touch_updated_at();;

create trigger trg_touch_export_jobs before update on public.export_jobs for each row execute function public.touch_updated_at();;

create trigger trg_touch_api_keys before update on public.api_keys for each row execute function public.touch_updated_at();;

create trigger trg_touch_usage_events before update on public.usage_events for each row execute function public.touch_updated_at();;

INSERT INTO alembic_version (version_num) VALUES ('0001_initial') RETURNING alembic_version.version_num;

COMMIT;


-- ============================================================
-- Row Level Security
-- ============================================================

-- Row-Level Security policies + helper functions for tenant isolation (§14).
-- Run against the Supabase Postgres project once the application schema exists.

-- Helper functions used by all policies. SECURITY DEFINER so the calling role
-- (authenticated) can rely on membership checks without exposing join internals.
create or replace function public.is_org_member(org_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = org_id
      and m.user_id = auth.uid()
  );
$$;

create or replace function public.has_org_role(org_id uuid, allowed_roles text[])
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = org_id
      and m.user_id = auth.uid()
      and m.role = any(allowed_roles)
  );
$$;

-- Enable RLS on all tenant-owned tables.
do $$
declare t text;
begin
  foreach t in array array[
    'users','organizations','organization_members','suppliers','invoices',
    'invoice_parties','invoice_line_items','invoice_tax_breakdowns',
    'extraction_fields','extraction_warnings','extraction_jobs','export_jobs',
    'usage_events','audit_logs','api_keys'
  ] loop
    execute format('alter table public.%I enable row level security;', t);
  end loop;
end $$;

-- users: a user can only see their own profile row.
create policy users_select_self on public.users
  for select using (auth.uid() = id);
create policy users_update_self on public.users
  for update using (auth.uid() = id);

-- organizations: members can select; only owners can update/delete.
create policy orgs_member_select on public.organizations
  for select using (public.is_org_member(id));
create policy orgs_owner_update on public.organizations
  for update using (public.has_org_role(id, array['owner']));
create policy orgs_owner_delete on public.organizations
  for delete using (public.has_org_role(id, array['owner']));

-- organization_members: members of the org can read; owners/admins manage.
create policy members_member_select on public.organization_members
  for select using (public.is_org_member(organization_id));
create policy members_admin_insert on public.organization_members
  for insert with check (public.has_org_role(organization_id, array['owner','admin']));
create policy members_admin_update on public.organization_members
  for update using (public.has_org_role(organization_id, array['owner','admin']));
create policy members_admin_delete on public.organization_members
  for delete using (public.has_org_role(organization_id, array['owner','admin']));

-- One helper for org-owned child tables.
do $$
declare t text; col text := 'organization_id';
begin
  foreach t in array array[
    'suppliers','invoices','export_jobs','usage_events','audit_logs','api_keys'
  ] loop
    execute format(
      'create policy %1$s_member_select on public.%1$s for select using (public.is_org_member(%2$I));',
      t, col);
  end loop;
end $$;

-- invoices + children: derive organization via invoice_id.
create policy invoices_list on public.invoices
  for select using (public.is_org_member(organization_id));
create policy invoices_insert on public.invoices
  for insert with check (public.has_org_role(organization_id, array['owner','admin','member']));
create policy invoices_update on public.invoices
  for update using (public.is_org_member(organization_id));
create policy invoices_delete on public.invoices
  for delete using (public.has_org_role(organization_id, array['owner']));

-- child tables of invoices join via invoice_id
create or replace function public.invoice_org_id(inv_id uuid)
returns uuid language sql stable security definer as $$
  select organization_id from public.invoices where id = inv_id;
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'invoice_parties','invoice_line_items','invoice_tax_breakdowns',
    'extraction_fields','extraction_warnings','extraction_jobs'
  ] loop
    execute format(
      'create policy %1$s_member_select on public.%1$s for select '
      'using (public.is_org_member(public.invoice_org_id(invoice_id)));', t);
    execute format(
      'create policy %1$s_member_update on public.%1$s for update '
      'using (public.is_org_member(public.invoice_org_id(invoice_id)));', t);
    execute format(
      'create policy %1$s_member_insert on public.%1$s for insert '
      'with check (public.is_org_member(public.invoice_org_id(invoice_id)));', t);
    execute format(
      'create policy %1$s_member_delete on public.%1$s for delete '
      'using (public.is_org_member(public.invoice_org_id(invoice_id)));', t);
  end loop;
end $$;