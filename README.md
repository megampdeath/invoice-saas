# Invoice Extraction SaaS

Implementation of the invoice extraction SaaS described in
[`INVOICE_SAAS_PLANNING.md`](./INVOICE_SAAS_PLANNING.md). The first version is
the reliable workflow:

```
Upload invoice → extract key fields → review quickly → approve → export
```

## Layout

```
backend/      FastAPI app + Alembic migrations + extraction/storage/providers
frontend/     Next.js app (placeholder)
supabase/     RLS + storage policy SQL
docker-compose.yml
.env          Environment (loaded by backend)
```

## Backend

### Install (local)

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e .
```

### Run migrations (against Supabase Postgres from `.env`)

```bash
cd backend
alembic upgrade head
```

Then apply RLS + storage policies in the Supabase Studio SQL editor:

```
supabase/rls.sql
supabase/storage-policies.sql
```

### Start the API and worker

```bash
uvicorn app.main:app --reload              # API
rq worker invoices exports                # background extraction + export worker
```

### Extraction provider

`EXTRACTION_PROVIDER` in `.env` selects the provider:

- `mock` — deterministic fake data (default for tests/local dev)
- `pdf_text` — digital-PDF text extraction with rules
- `textract` — AWS Textract AnalyzeExpense (uses AWS_* env vars)

### Health & quick checks

```bash
curl http://localhost:8000/
curl http://localhost:8000/api/health
```

## Frontend (placeholder)

The Next.js frontend is scaffolded separately; the backend is the source of
truth for the `INVOICE_SAAS_PLANNING.md` API contract in §7.

## Docker

```bash
docker compose up          # redis + api + worker + frontend
```

## Notes / status

- Milestone 1 (foundation): config wired to `.env`, Supabase Postgres engine
  (lazy), SQLAlchemy models, Alembic initial migration, Supabase JWT verification,
  organization-based authorization, RLS SQL.
- Milestone 2-3 (upload + background processing): upload endpoint, Supabase/local
  storage abstraction with signed URLs, extraction job queueing (RQ with inline
  dev fallback), mock provider, status transitions.
- Milestone 4 (review): invoice detail, update/approve/archive/delete/reprocess
  endpoints with validation warnings + audit logs. Frontend review screen with
  PDF/image preview beside editable fields.
- Milestone 5 (real text extraction): `pdf_text` provider + normalization rules.
- Milestone 6 (export): CSV/XLSX export jobs with Supabase Storage signed URLs.
- Milestone 7 (billing): usage tracking per billing period, plan limits enforced
  at upload, Stripe Checkout + webhook handling (subscription create/update/delete,
  payment succeeded/failed), usage + upgrade UI in settings.
- Milestone 8 (external OCR): AWS Textract `AnalyzeExpense` adapter implemented.
  Mindee/Azure/Google adapters + bake-off script still pending.

### Tests

42 unit tests cover normalization (amounts/dates/currency/VAT/supplier),
validation warnings + confidence weighting + duplicate detection, mock/pdf_text
extraction providers, storage path sanitization, role permissions, and billing
plan limits:

```bash
cd backend && python -m pytest app/tests -q
```

### Frontend

Next.js App Router with Supabase Auth, sidebar app shell, invoice inbox with
upload dropzone + filters, split-pane review screen (preview + editable fields),
suppliers, exports, and settings (plan usage + Stripe upgrade).

```bash
cd frontend && npm install && npm run dev
```

### What still needs doing

- Apply `supabase/rls.sql` + storage policies in the Supabase dashboard.
- Run `alembic upgrade head` against the live Supabase Postgres.
- Set Stripe price IDs + webhook secret in `.env` for billing to be live.
- Milestone 8: remaining OCR adapters (Mindee/Azure/Google) + bake-off script.
- Integration tests requiring a live DB, and frontend component tests.