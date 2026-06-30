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