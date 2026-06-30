# Invoice Extraction SaaS Planning Document

This document is a detailed build plan for an invoice extraction SaaS. It is written so a coding agent can implement the product without needing additional product discovery.

## 1. Product Summary

Build a SaaS where businesses upload supplier invoices as PDF/image files, automatically extract accounting fields, review and correct the extracted data, then export clean structured data to CSV/XLSX. The initial product should prioritize reliable workflow and human review over pretending extraction is perfect.

### Core Promise

"Upload messy invoices. Get clean accounting-ready data."

### Initial Target Customer

Small businesses, accounting firms, finance/admin teams, and agencies that manually enter invoice data into spreadsheets or accounting software.

### Initial Positioning

Invoice extraction and review SaaS for French/EU-style invoices, with VAT-aware validation and export-ready structured data.

### Non-Goals For MVP

- Do not build full accounting software.
- Do not build bank reconciliation.
- Do not build payment execution.
- Do not build every accounting integration immediately.
- Do not require perfect line-item extraction in version 1.
- Do not expose a public API until the web workflow is reliable.

## 2. MVP Scope

The MVP must support:

- User signup/login.
- Organization/workspace creation.
- Upload invoice PDFs/images.
- Store original files securely.
- Process files asynchronously.
- Extract invoice fields.
- Display invoice preview beside extracted fields.
- Allow users to correct extracted fields.
- Save corrected invoice data.
- Track extraction confidence and warnings.
- Export reviewed invoices to CSV and XLSX.
- Basic subscription limits by invoice/page count.

### MVP Fields To Extract

Required fields:

- Supplier/vendor name
- Supplier VAT number/tax ID
- Invoice number
- Invoice date
- Due date
- Currency
- Subtotal/net amount
- Tax/VAT amount
- Total/gross amount

Optional fields:

- Customer name
- Supplier address
- Customer address
- IBAN
- Payment terms
- Document language
- Purchase order number
- Notes/raw text

Line items:

- Store line items if provider returns them.
- Do not block MVP launch on perfect line-item extraction.
- The review UI may show line items behind an "Advanced" panel.

## 3. Recommended Tech Stack

Use this default stack. The product should use Supabase for auth, database, file storage, signed URLs, and tenant security. Use Render for application compute and background workers.

- Frontend: Next.js with TypeScript
- UI: Tailwind CSS plus a simple component system
- Frontend hosting: Render Web Service or Render Static Site
- Backend API: FastAPI with Python on Render
- Database: Supabase Postgres
- ORM/migrations: SQLAlchemy + Alembic
- Auth: Supabase Auth
- File storage: Supabase Storage
- Background jobs: Redis + RQ on Render
- Worker hosting: Render Background Worker
- OCR/extraction provider: provider abstraction with a mock provider first, then a paid provider selected by a real invoice bake-off
- Billing: Stripe
- Deployment target: Docker containers deployed to Render

### Why This Stack

- Next.js gives a modern SaaS frontend.
- FastAPI is strong for file handling, OCR provider integration, and Python document processing.
- Supabase gives secure managed Postgres, authentication, storage, signed URLs, and row-level security in one platform.
- Render keeps the API, frontend, and worker deployment simple without self-managing servers.
- Redis workers avoid slow upload requests and keep OCR processing outside request/response paths.
- Supabase Storage keeps uploaded files out of the database while preserving per-organization access controls.

### Locked MVP Infrastructure Decisions

- Use Supabase for auth, Postgres, Storage, signed URLs, and row-level security.
- Use Render for the Next.js frontend, FastAPI backend, Redis, and worker.
- Use Supabase Storage instead of S3 for invoice originals, OCR raw output when retained, and generated exports.
- Use Supabase Auth only; do not implement custom passwords or JWT signing.
- Use SQLAlchemy + Alembic for application schema migrations against Supabase Postgres.
- Use Redis + RQ for background jobs because it is simple, Python-native, and easy to run on Render.
- Use AWS Textract as the first production external OCR default for scanned invoices unless the bake-off proves Mindee, Azure, or Google is materially better.

## 4. High-Level Architecture

```text
User Browser
  -> Next.js Web App on Render
     -> Supabase Auth
  -> FastAPI Backend on Render
     -> Supabase Postgres
     -> Supabase Storage
     -> Render Redis Queue
        -> Render Worker
           -> OCR/Extraction Provider
           -> Normalization
           -> Validation
           -> Supabase Postgres Update
```

### Deployment Ownership

- Supabase owns managed auth, Postgres, storage buckets, signed file URLs, and database row-level security.
- Render owns the Next.js frontend, FastAPI backend, Redis instance, and background worker.
- Stripe owns checkout, subscriptions, invoices, and payment method handling.
- OCR providers own extraction APIs only. Their raw responses should be stored only when needed for debugging and never exposed directly to end users.

### Processing Flow

1. User uploads invoice file.
2. Backend validates file type and size.
3. Backend creates an invoice row with status `uploaded`.
4. Backend stores original file in private Supabase Storage.
5. Backend enqueues an extraction job.
6. Worker downloads the file.
7. Worker runs OCR/extraction.
8. Worker normalizes extracted fields.
9. Worker validates totals/dates/VAT format.
10. Worker saves extracted fields, raw text, confidence, and warnings.
11. Invoice status becomes `needs_review` or `failed`.
12. User reviews and corrects data.
13. User marks invoice as `approved`.
14. User exports approved invoices.

## 5. Core Status Model

Use these invoice statuses:

- `uploaded`: file accepted but not processed.
- `processing`: worker is extracting data.
- `needs_review`: extraction completed and requires user review.
- `approved`: user reviewed and accepted/corrected data.
- `failed`: extraction failed.
- `archived`: hidden from active workflows.

Use these job statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `retrying`

## 6. Database Schema

Use UUID primary keys for externally visible IDs.

### users

Supabase Auth owns credentials, sessions, password reset, email verification, and OAuth identities in `auth.users`. The application `users` table is only a profile/mapping table. Do not store password hashes in the application schema.

```sql
id uuid primary key references auth.users(id) on delete cascade
email text not null unique
name text
avatar_url text
auth_provider text
created_at timestamptz not null
updated_at timestamptz not null
```

Create the application profile row through a Supabase Auth trigger or on first successful login. The backend should verify Supabase access tokens before accepting API requests.

### organizations

```sql
id uuid primary key
name text not null
slug text not null unique
billing_email text
stripe_customer_id text
stripe_subscription_id text
subscription_status text not null default 'free'
plan text not null default 'free'
usage_period_start date
usage_period_end date
created_at timestamptz not null
updated_at timestamptz not null
```

### organization_members

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
user_id uuid not null references users(id)
role text not null
created_at timestamptz not null
unique(organization_id, user_id)
```

Valid roles:

- `owner`
- `admin`
- `member`
- `viewer`

Role permissions:

| Permission | owner | admin | member | viewer |
| --- | --- | --- | --- | --- |
| View invoices and files | yes | yes | yes | yes |
| Upload invoices | yes | yes | yes | no |
| Edit extracted fields | yes | yes | yes | no |
| Approve invoices | yes | yes | yes | no |
| Export approved invoices | yes | yes | yes | no |
| Reprocess invoices | yes | yes | yes | no |
| Archive invoices | yes | yes | yes | no |
| Hard-delete invoices | yes | no | no | no |
| Manage suppliers | yes | yes | yes | no |
| Invite or remove members | yes | yes | no | no |
| Change member roles | yes | yes | no | no |
| Manage billing and plan | yes | no | no | no |
| Manage retention settings | yes | no | no | no |
| Manage future API keys | yes | yes | no | no |

### invoices

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
uploaded_by_user_id uuid not null references users(id)
status text not null
original_filename text not null
file_mime_type text not null
file_size_bytes bigint not null
storage_key text not null
page_count integer
document_hash text
duplicate_of_invoice_id uuid null references invoices(id)
supplier_id uuid null references suppliers(id)
invoice_number text
invoice_date date
due_date date
currency text
subtotal_amount numeric(14, 2)
tax_amount numeric(14, 2)
total_amount numeric(14, 2)
iban text
payment_terms text
raw_text text
extraction_confidence numeric(5, 4)
reviewed_by_user_id uuid null references users(id)
reviewed_at timestamptz
created_at timestamptz not null
updated_at timestamptz not null
```

### invoice_parties

Use this if customer/vendor data may be richer than the simple invoice row.

```sql
id uuid primary key
invoice_id uuid not null references invoices(id)
party_type text not null
name text
vat_number text
tax_id text
address_line1 text
address_line2 text
postal_code text
city text
country_code text
created_at timestamptz not null
updated_at timestamptz not null
```

Valid `party_type` values:

- `supplier`
- `customer`

### suppliers

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
name text not null
normalized_name text
vat_number text
tax_id text
iban text
default_expense_category text
created_at timestamptz not null
updated_at timestamptz not null
```

### invoice_line_items

```sql
id uuid primary key
invoice_id uuid not null references invoices(id)
line_number integer
description text
quantity numeric(14, 4)
unit_price numeric(14, 4)
tax_rate numeric(7, 4)
tax_amount numeric(14, 2)
total_amount numeric(14, 2)
confidence numeric(5, 4)
created_at timestamptz not null
updated_at timestamptz not null
```

### invoice_tax_breakdowns

Use this for EU invoices with multiple VAT rates, exemptions, or reverse-charge cases.

```sql
id uuid primary key
invoice_id uuid not null references invoices(id)
tax_rate numeric(7, 4)
taxable_amount numeric(14, 2)
tax_amount numeric(14, 2)
total_amount numeric(14, 2)
label text
created_at timestamptz not null
updated_at timestamptz not null
```

### extraction_fields

Store field-level confidence and source metadata here.

```sql
id uuid primary key
invoice_id uuid not null references invoices(id)
field_name text not null
raw_value text
normalized_value text
confidence numeric(5, 4)
source text
page_number integer
bbox_json jsonb
created_at timestamptz not null
updated_at timestamptz not null
unique(invoice_id, field_name)
```

### extraction_warnings

```sql
id uuid primary key
invoice_id uuid not null references invoices(id)
code text not null
message text not null
severity text not null
created_at timestamptz not null
```

Valid severities:

- `info`
- `warning`
- `error`

Example warning codes:

- `low_confidence_total`
- `missing_invoice_number`
- `subtotal_tax_total_mismatch`
- `invalid_vat_format`
- `duplicate_invoice_detected`
- `line_items_not_extracted`
- `ocr_provider_failed`

### extraction_jobs

Track each processing attempt independently from the invoice row.

```sql
id uuid primary key
invoice_id uuid not null references invoices(id)
status text not null
provider text not null
attempt integer not null default 1
max_attempts integer not null default 3
queued_at timestamptz not null
started_at timestamptz
finished_at timestamptz
error_code text
error_message text
raw_result_storage_key text
created_at timestamptz not null
updated_at timestamptz not null
```

Valid statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `retrying`

### export_jobs

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
created_by_user_id uuid not null references users(id)
status text not null
format text not null
filter_json jsonb
storage_key text
row_count integer
created_at timestamptz not null
updated_at timestamptz not null
```

### api_keys

Keep this for later API access.

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
name text not null
key_prefix text not null
key_hash text not null
last_used_at timestamptz
created_at timestamptz not null
revoked_at timestamptz
```

### usage_events

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
event_type text not null
quantity integer not null
metadata_json jsonb
created_at timestamptz not null
```

Example event types:

- `invoice_uploaded`
- `page_processed`
- `invoice_exported`
- `api_request`

### audit_logs

Use audit logs for security-sensitive events and support investigations. Do not store raw invoice text here.

```sql
id uuid primary key
organization_id uuid not null references organizations(id)
actor_user_id uuid null references users(id)
action text not null
target_type text
target_id uuid
metadata_json jsonb
created_at timestamptz not null
```

Example actions:

- `invoice.uploaded`
- `invoice.approved`
- `invoice.archived`
- `invoice.deleted`
- `invoice.exported`
- `member.invited`
- `member.role_changed`
- `billing.plan_changed`
- `storage.signed_url_created`

## 7. Backend API Endpoints

Prefix all backend endpoints with `/api`.

### Auth / Current User

Supabase Auth handles signup, login, logout, password reset, email verification, and OAuth if enabled. The frontend sends the Supabase access token to the FastAPI backend as a bearer token.

```http
Authorization: Bearer <supabase_access_token>
```

```http
GET /api/me
```

Returns current user, organizations, active organization, role, plan, and usage period. The backend must verify the Supabase JWT and map `sub` to `users.id` before loading organization data.

### Organizations

```http
POST /api/organizations
GET /api/organizations
GET /api/organizations/{organization_id}
PATCH /api/organizations/{organization_id}
GET /api/organizations/{organization_id}/members
POST /api/organizations/{organization_id}/members/invite
PATCH /api/organizations/{organization_id}/members/{member_id}
DELETE /api/organizations/{organization_id}/members/{member_id}
```

Behavior:

- New users should get a default organization during onboarding unless they joined through an invite.
- Owners can manage billing and retention.
- Owners and admins can invite/remove members and change roles.
- The last owner cannot be removed or downgraded.

### Invoice Upload

```http
POST /api/invoices
Content-Type: multipart/form-data
```

Request fields:

- `file`: PDF/JPG/JPEG/PNG/TIFF
- `organization_id`: UUID

Default upload limits:

- Max file size: 25 MB per file.
- Max page count: 50 pages per invoice file.
- Single upload endpoint accepts one file. Batch upload can be added later as a thin loop over the same endpoint.
- TIFF support is allowed only if the backend can reliably count pages and preview it; otherwise reject TIFF with a clear error in MVP.

Response:

```json
{
  "id": "uuid",
  "status": "uploaded",
  "original_filename": "invoice.pdf"
}
```

Behavior:

- Validate Supabase auth and organization membership.
- Validate role permission to upload.
- Validate plan usage limits before extraction starts.
- Accept only allowed MIME types and verify file signatures where possible.
- Enforce file size and page count limits.
- Compute SHA-256 hash.
- Detect duplicate document hash within organization.
- Save file to a private Supabase Storage bucket using a non-guessable path such as `{organization_id}/originals/{invoice_id}/{safe_filename}`.
- Create invoice record.
- Create an `extraction_jobs` row.
- Queue extraction job in Render Redis/RQ.

### Invoice List

```http
GET /api/invoices?organization_id=...&status=needs_review&search=...&from=2026-01-01&to=2026-12-31
```

Return paginated list:

```json
{
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 123
}
```

### Invoice Detail

```http
GET /api/invoices/{invoice_id}
```

Return:

- Invoice metadata
- Extracted fields
- Supplier/customer parties
- Line items
- Warnings
- Secure short-lived file preview URL

### Update Invoice

```http
PATCH /api/invoices/{invoice_id}
```

Allow user corrections:

```json
{
  "invoice_number": "FA-2026-001",
  "invoice_date": "2026-06-23",
  "due_date": "2026-07-23",
  "currency": "EUR",
  "subtotal_amount": 1000.0,
  "tax_amount": 200.0,
  "total_amount": 1200.0,
  "supplier": {
    "name": "Example SARL",
    "vat_number": "FR12345678901"
  }
}
```

After update:

- Re-run validations.
- Recalculate warnings.
- Update supplier memory if appropriate.

### Approve Invoice

```http
POST /api/invoices/{invoice_id}/approve
```

Behavior:

- Requires status `needs_review`.
- Requires role permission to approve.
- Requires supplier name, invoice number, invoice date, currency, and total amount.
- Blocks approval on `error` warnings unless the warning is explicitly marked as manually accepted.
- Allows `info` and non-blocking `warning` warnings after user review.
- Sets status `approved`.
- Sets reviewer and reviewed timestamp.
- Writes an audit log event.

### Reprocess Invoice

```http
POST /api/invoices/{invoice_id}/reprocess
```

Behavior:

- Re-queue extraction job.
- Keep original file.
- Store new extraction results.
- Do not delete user corrections unless explicitly requested.

### Delete / Archive Invoice

```http
POST /api/invoices/{invoice_id}/archive
DELETE /api/invoices/{invoice_id}
```

Soft archive by default. Hard delete is owner-only and should remove database records, Supabase Storage objects, generated export files when relevant, and related derived extraction data according to the retention policy. Deletion should write an audit log event without storing invoice contents.

### Export

```http
POST /api/exports
```

Request:

```json
{
  "organization_id": "uuid",
  "format": "xlsx",
  "status": "approved",
  "from": "2026-01-01",
  "to": "2026-12-31"
}
```

Response:

```json
{
  "export_job_id": "uuid",
  "status": "queued"
}
```

```http
GET /api/exports/{export_job_id}
```

Return status and a short-lived Supabase signed download URL when ready.

Export defaults:

- Only export approved invoices unless the user explicitly filters otherwise and has permission.
- CSV delimiter: comma.
- CSV encoding: UTF-8.
- Decimal format: dot decimal separator with two decimals for money.
- Date format: ISO `YYYY-MM-DD`.
- Datetime format: ISO 8601 UTC.
- XLSX filename: `invoices-export-{YYYYMMDD-HHMMSS}.xlsx`.
- CSV filename: `invoices-export-{YYYYMMDD-HHMMSS}.csv`.
- Warning values should be serialized as semicolon-separated warning codes.

## 8. Future Public API

Build after the SaaS review workflow is stable.

```http
POST /v1/invoices/extract
GET /v1/invoices/{id}
POST /v1/invoices/batch
POST /v1/webhooks
GET /v1/usage
```

Authentication:

```http
Authorization: Bearer sk_live_...
```

Public API response must include:

- Structured fields
- Field-level confidence
- Warnings
- Raw text optional
- Processing status

## 9. Frontend Pages

### `/login`

Purpose:

- Authenticate user.

Requirements:

- Email/password or hosted auth provider.
- Redirect authenticated users to `/app/invoices`.

### `/app`

Purpose:

- Main app layout with sidebar navigation.

Sidebar items:

- Inbox
- Review
- Approved
- Suppliers
- Exports
- Settings

### `/app/invoices`

Purpose:

- Invoice inbox and dashboard.

Must show:

- Upload button/dropzone.
- List/table of invoices.
- Status filter.
- Search box.
- Date filter.
- Counts by status.

Table columns:

- File/invoice number
- Supplier
- Invoice date
- Total
- Currency
- Status
- Warnings
- Uploaded date

Bulk actions:

- Export selected
- Archive selected
- Reprocess selected

### `/app/invoices/[id]`

Purpose:

- Review and correct one invoice.

Layout:

- Left side: PDF/image preview.
- Right side: editable extracted fields.
- Top bar: status, confidence, actions.

Actions:

- Save changes
- Approve
- Reprocess
- Archive
- Download original

Field behavior:

- Low-confidence fields should be visually marked.
- Warnings should appear near relevant fields.
- Totals mismatch should show a clear warning.
- Date fields should use date inputs.
- Currency should use a select/input.
- Amount fields should use numeric inputs.

Do not place the invoice preview inside a decorative card. Make the review experience efficient and dense.

### `/app/suppliers`

Purpose:

- Manage supplier memory.

Must show:

- Supplier name
- VAT number
- Default category
- IBAN
- Number of invoices
- Last invoice date

### `/app/exports`

Purpose:

- Export history and download links.

Must show:

- Export format
- Filter summary
- Created date
- Status
- Download button

### `/app/settings`

Purpose:

- Organization and billing settings.

Sections:

- Organization profile
- Team members
- Plan and usage
- Data retention
- API keys later

## 10. UX Requirements

The review workflow is the heart of the product. Optimize for speed and trust.

### Review Screen Must-Haves

- PDF/image preview is visible while editing fields.
- User can zoom, pan, and switch pages.
- Keyboard-friendly form navigation.
- Save state must be clear.
- Low-confidence values must be easy to spot.
- Warnings must be specific and actionable.
- User must be able to approve in one click after fields look correct.

### Empty States

Inbox empty state should encourage upload and explain accepted file types in one short sentence.

### Loading States

Processing invoices should show:

- `uploaded`
- `processing`
- `needs_review`
- `failed`

### Error States

Extraction failure must not lose the uploaded file. User should be able to:

- Retry extraction.
- Download original.
- Manually enter invoice fields.

## 11. Extraction Engine

Create an extraction provider interface so the product can switch providers later.

### Interface

```python
class InvoiceExtractionProvider:
    def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        ...
```

### ExtractionResult Shape

```python
{
  "raw_text": "...",
  "fields": {
    "invoice_number": {
      "value": "FA-2026-001",
      "confidence": 0.92,
      "page": 1,
      "bbox": null
    },
    "total_amount": {
      "value": "1200.00",
      "confidence": 0.98,
      "page": 1,
      "bbox": null
    }
  },
  "line_items": [],
  "provider": "mock"
}
```

### Provider Implementations

Implement in this order:

1. `MockExtractionProvider`
   - Used for local development and tests.
   - Returns deterministic fake data.

2. `TextPdfExtractionProvider`
   - Extracts text from digital PDFs.
   - Uses a Python PDF library.
   - Applies simple regex/rules for invoice number, dates, totals, VAT.

3. `ExternalOcrExtractionProvider`
   - Wraps a paid provider.
   - Default production adapter: AWS Textract AnalyzeExpense unless the invoice bake-off proves another provider is materially better.
   - Keep credentials in environment variables.
   - Never leak provider response to the user without filtering.

MVP OCR decision:

- Customer-facing MVP must support digital PDFs through text extraction and scanned PDFs/images through the selected external OCR provider.
- Mock extraction is for local development and tests only.
- If external OCR is not ready, scanned/image uploads may be accepted only with a clear manual-entry fallback and must be marked `needs_review` with an extraction warning.

Provider-specific adapters to prepare:

- `MindeeInvoiceProvider`
- `AwsTextractExpenseProvider`
- `GoogleDocumentAiInvoiceProvider`
- `AzureDocumentIntelligenceInvoiceProvider`

Optional later:

- LLM normalization after OCR.
- Provider fallback chain.
- Per-customer custom templates.

### OCR Provider Comparison And Recommendation

This provider comparison was reviewed on 2026-06-23. Re-check provider pricing, data residency, feature availability, and model versions before launch.

| Provider | Best Use | Strengths | Risks | Pricing Shape |
| --- | --- | --- | --- | --- |
| Mindee Invoice OCR | Fastest demo and fastest SaaS workflow prototype. Good if you want a focused invoice API without deep cloud setup. | Prebuilt invoice model, custom schema option, PDF/image support, SDKs/no-code integrations, EU or US hosting, and strong invoice-specific fields including totals, dates, taxes, supplier details, VAT, line items, IBAN, and payment terms. | The public pricing page clearly lists confidence scores in Business/Enterprise plan sections; confirm confidence availability before relying on it for the review UI. Starter/Pro may be weaker for compliance/data-localization needs. | Public annual-billing examples: Starter 500 credits/month and +EUR0.05/additional credit; Pro 2,500 credits/month and +EUR0.04/additional credit; Business 10,000 credits/month and +EUR0.035/additional credit. |
| AWS Textract AnalyzeExpense | Best first production default if low cost and field confidence are required from day one. | Invoice/receipt extraction without templates, standardized taxonomy, confidence values, geometry, line items, sync and async APIs, and low per-page cost. | AWS setup is more operationally heavy. Output normalization is more work than Mindee. Language and regional fit must be tested with real French/EU invoices. | AWS pricing example: Analyze Expense is USD0.01/page for the first 1M pages in US West (Oregon), then USD0.008/page after 1M. Free tier includes 100 pages/month for 3 months for new AWS customers. |
| Google Document AI Invoice Parser | Best when customers already trust Google Cloud, need Google Document AI tooling, or may later need custom processors. | General availability invoice parser, header and line-item extraction, entity confidence, normalized values, EU region support, and supported invoice languages including French, English, German, Spanish, Italian, Dutch, Portuguese, and more. | Pricing is per 10-page document block, so one-page invoices can be more expensive unless pricing is passed through. Google Cloud setup is heavier than Mindee. | Listed pricing example: parsing a document with 1-10 pages costs USD0.10, 11-20 pages costs USD0.20, and 91-100 pages costs USD1. |
| Azure Document Intelligence Prebuilt Invoice | Best for Microsoft-heavy customers, broad language coverage, and enterprise procurement/compliance fit. | Prebuilt invoice model, line-item extraction, structured JSON, 27 supported invoice languages, confidence scores, Document Intelligence Studio, and generous paid-tier file/page limits. | Pricing is region/currency dynamic on Azure's public page, so exact cost must be checked in the Azure calculator. Integration is not as quick as Mindee. | Free tier exists but is limited. Standard tier supports larger files/pages. Paid pricing is per 1,000 pages with commitment tiers; check exact region pricing before launch. |

Recommendation:

- Keep the provider interface mandatory. Never hardcode one vendor into invoice processing.
- For a quick customer demo, Mindee is still the fastest path.
- For a commercial MVP with low cost of goods and field confidence from day one, implement AWS Textract AnalyzeExpense first unless the sample bake-off proves another provider is more accurate.
- If the target customers are Microsoft-heavy accountants or enterprise teams, test Azure early.
- If the target customers are already on Google Cloud or need custom Document AI processors later, test Google early.

Provider bake-off before launch:

1. Collect 25-50 real sample invoices from the target customer segment.
2. Run each invoice through Mindee, AWS, Azure, and Google where accounts are available.
3. Save raw provider output, normalized output, latency, cost, warnings, and required human corrections.
4. Score providers by field accuracy, line-item usefulness, confidence usefulness, EU/French invoice support, latency, failure rate, and all-in cost.
5. Confirm AWS Textract as the production default, or override it, only after this test.

Provider source URLs to re-check:

- Mindee invoice docs: `https://www.mindee.com/product/invoice-ocr-api`
- Mindee pricing: `https://www.mindee.com/pricing`
- Mindee data policy: `https://docs.mindee.com/models/data-processing-policies`
- AWS Textract invoices: `https://docs.aws.amazon.com/textract/latest/dg/invoices-receipts.html`
- AWS Textract AnalyzeExpense API: `https://docs.aws.amazon.com/textract/latest/APIReference/API_AnalyzeExpense.html`
- AWS Textract pricing: `https://aws.amazon.com/textract/pricing/`
- Google Document AI processor list: `https://docs.cloud.google.com/document-ai/docs/processors-list`
- Google Document AI pricing: `https://cloud.google.com/document-ai/pricing`
- Azure invoice model: `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/invoice`
- Azure confidence docs: `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/accuracy-confidence`
- Azure limits: `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits`
- Azure pricing: `https://azure.microsoft.com/en-us/pricing/details/document-intelligence/`

### Normalization Rules

Dates:

- Normalize to ISO `YYYY-MM-DD`.
- Handle common EU formats: `DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`.

Amounts:

- Normalize decimal separators.
- Handle `1 234,56`, `1,234.56`, `1234.56`.
- Store numeric decimal values.

Currency:

- Detect `EUR`, `USD`, `GBP`, `MAD`, and common currency symbols.
- Store ISO currency code.

VAT:

- Strip spaces.
- Uppercase.
- Validate format at least syntactically.
- For EU VAT validation, add provider/service later.

Supplier name:

- Trim whitespace.
- Remove obvious OCR line noise.
- Store raw and normalized values.

## 12. Validation Logic

Run validation after extraction and after every user edit.

### Required Field Checks

Warn if missing:

- Supplier name
- Invoice number
- Invoice date
- Total amount
- Currency

### Amount Checks

If subtotal, tax, and total are present:

```text
subtotal + tax should equal total within 0.02 tolerance
```

If line items are present:

```text
sum(line item totals) should equal subtotal or total depending on tax inclusion
```

### Date Checks

Warn if:

- Due date is before invoice date.
- Invoice date is implausibly old or in the future.

### Duplicate Checks

Flag possible duplicate if same organization has:

- same supplier + invoice number, or
- same document hash, or
- same supplier + total + invoice date.

### Confidence Rules

Overall confidence can be weighted:

```text
invoice_number: 15%
supplier_name: 20%
invoice_date: 15%
total_amount: 25%
tax_amount: 10%
subtotal_amount: 10%
currency: 5%
```

Set invoice to `needs_review` even when confidence is high. The first SaaS version should require human approval before export.

## 13. Export Format

CSV/XLSX columns:

- invoice_id
- status
- supplier_name
- supplier_vat_number
- invoice_number
- invoice_date
- due_date
- currency
- subtotal_amount
- tax_amount
- total_amount
- iban
- payment_terms
- original_filename
- uploaded_at
- reviewed_at
- warnings

XLSX should include:

- Header row styling.
- Currency/amount number formatting.
- Date formatting.
- One row per invoice.

Do not include raw OCR text by default in exports.

## 14. Security And Privacy

Invoices contain sensitive business data. Supabase is acceptable for this product if it is configured with strict tenant isolation and private file access from the beginning.

Implement these from the beginning:

- Organization-based authorization on every invoice endpoint.
- Supabase Row Level Security enabled on all tenant-owned tables exposed through Supabase APIs.
- Backend authorization checks in FastAPI even when RLS exists. Treat RLS as defense in depth, not the only gate.
- Never allow users to access another organization's files.
- Store files in private Supabase Storage buckets with non-guessable paths.
- Use signed short-lived URLs for previews/downloads. Default expiry: 10 minutes.
- Keep Supabase secret/service-role keys server-side only. Never expose them to the browser or logs.
- The browser may use only the public/publishable Supabase key and user-scoped access token.
- Enforce upload file type, file signature, file size, and page count.
- Scan or reject suspicious file types.
- Keep API keys hashed, never stored plaintext.
- Log security-sensitive events in `audit_logs`.
- Avoid logging raw invoice text, supplier bank details, VAT IDs, or extracted sensitive data.
- Add configurable retention later.

### Supabase Security Baseline

- Enable RLS on `users`, `organizations`, `organization_members`, `invoices`, `invoice_parties`, `suppliers`, `invoice_line_items`, `invoice_tax_breakdowns`, `extraction_fields`, `extraction_warnings`, `export_jobs`, `usage_events`, and `audit_logs`.
- Use helper SQL functions such as `is_org_member(org_id uuid)` and `has_org_role(org_id uuid, allowed_roles text[])` to keep policies consistent.
- Keep invoice original files in a private `invoice-originals` bucket.
- Keep generated exports in a private `invoice-exports` bucket.
- Store OCR raw provider payloads, if retained at all, in a private `ocr-raw-results` bucket with owner/admin-only access and short retention.
- Generate preview/download URLs only from the FastAPI backend after checking organization membership and role permissions.
- Use Supabase Security Advisor before launch and fix all warnings related to exposed tables, disabled RLS, leaked keys, and unsafe functions.
- Enable Supabase backups and PITR before production customer data is stored, and document a restore runbook before first paid customer launch.

Supabase source URLs to re-check before launch:

- Supabase RLS docs: `https://supabase.com/docs/guides/database/postgres/row-level-security`
- Supabase Storage access control: `https://supabase.com/docs/guides/storage/security/access-control`
- Supabase signed downloads: `https://supabase.com/docs/guides/storage/serving/downloads`
- Supabase API keys: `https://supabase.com/docs/guides/api/api-keys`
- Supabase Security Advisor: `https://supabase.com/docs/guides/platform/security-advisor`

### Data Retention

Initial default:

- Keep uploaded files and extracted data until user deletes them.

Future:

- Auto-delete originals after N days.
- Retain structured data only.
- Organization-level retention settings.

## 15. Billing And Plans

Charge by pages or invoices processed, not by users only.

Suggested initial plans:

- Free: 20 invoices/month
- Starter: 200 invoices/month
- Pro: 1,000 invoices/month
- Business: custom

Usage rules:

- Count usage when extraction begins, not merely when a file is selected in the browser.
- Track page count when available.
- If page count is unavailable, count one uploaded file as one invoice.
- Prevent extraction when plan limit is exceeded.
- Block upload/extraction when the plan limit is exceeded and show a clear upgrade prompt. Manual-entry-only over-limit uploads can be added later if customers ask for it.
- Reset monthly usage based on `usage_period_start` and `usage_period_end` on the organization.
- Free plan has no Stripe subscription.
- Starter/Pro/Business plans map to Stripe price IDs stored in environment variables.
- Past-due subscriptions should keep read/export access but block new extraction after a short grace period.

Stripe events to handle:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`
- `invoice.payment_succeeded`

## 16. Environment Variables

Use these names:

```env
APP_ENV=development
APP_BASE_URL=
FRONTEND_BASE_URL=
BACKEND_BASE_URL=

DATABASE_URL=
DIRECT_DATABASE_URL=
REDIS_URL=

NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
SUPABASE_URL=
SUPABASE_SECRET_KEY=
SUPABASE_JWT_ISSUER=
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_STORAGE_ORIGINALS_BUCKET=invoice-originals
SUPABASE_STORAGE_EXPORTS_BUCKET=invoice-exports
SUPABASE_STORAGE_OCR_RAW_BUCKET=ocr-raw-results
STORAGE_BACKEND=supabase
LOCAL_STORAGE_DIR=./storage

EXTRACTION_PROVIDER=mock
OCR_PROVIDER_API_KEY=
MINDEE_API_KEY=
AWS_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
GOOGLE_DOCUMENT_AI_PROJECT_ID=
GOOGLE_DOCUMENT_AI_LOCATION=
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_KEY=

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_STARTER_MONTHLY=
STRIPE_PRICE_PRO_MONTHLY=
STRIPE_PRICE_BUSINESS_MONTHLY=
```

Rules:

- `NEXT_PUBLIC_*` values may be exposed to the browser.
- `SUPABASE_SECRET_KEY`, database URLs, OCR keys, and Stripe keys are backend/worker-only.
- Render environment groups should separate frontend-safe variables from backend/worker secrets.

## 17. Local Development

Provide Docker Compose with:

- Redis
- Backend API
- Worker
- Frontend

Use hosted Supabase for auth, Postgres, and storage by default during development so local behavior matches production. Optional later: add Supabase CLI for fully local development.

Local commands should include:

```bash
docker compose up
```

Backend:

```bash
alembic upgrade head
uvicorn app.main:app --reload
rq worker invoices
```

Frontend:

```bash
npm install
npm run dev
```

## 18. Testing Requirements

### Backend Unit Tests

Test:

- File validation.
- Organization authorization.
- Invoice status transitions.
- Amount normalization.
- Date normalization.
- VAT normalization.
- Duplicate detection.
- Validation warning generation.
- Export generation.
- Supabase JWT verification.
- Role permission checks.
- Supabase Storage path generation.

### Backend Integration Tests

Test:

- Upload creates invoice and queues job.
- Worker processes mock extraction result.
- Invoice detail returns extracted fields.
- User correction updates invoice.
- Approval requires required fields.
- Export returns valid CSV/XLSX.
- Private Supabase Storage objects are not publicly readable.
- Signed preview/download URLs require authorized backend requests.

### Frontend Tests

Test:

- Invoice list renders.
- Upload flow shows processing state.
- Review form saves changes.
- Low-confidence fields display visually.
- Approve button works.
- Export action starts export job.

### Manual QA

Use sample documents:

- Digital PDF invoice.
- Scanned PDF invoice.
- JPG invoice.
- Invoice missing due date.
- Invoice with VAT.
- Invoice with totals mismatch.
- Duplicate invoice.
- Low-quality scan.

## 19. Implementation Milestones

### Milestone 1: Project Foundation

Deliverables:

- Monorepo or clear frontend/backend folders.
- Docker Compose for app services.
- Supabase Postgres connection.
- Render Redis connection.
- Basic app shell.
- Supabase Auth integration.
- Organization model.
- Initial RLS policies for tenant-owned tables.

Acceptance criteria:

- User can sign up and log in through Supabase Auth.
- User gets or joins an organization.
- User can access `/app/invoices`.
- Backend health endpoint works.
- Alembic migrations run cleanly against Supabase Postgres.
- Basic RLS smoke tests pass.

### Milestone 2: Upload And Storage

Deliverables:

- Invoice upload endpoint.
- File validation.
- Supabase Storage adapter.
- Private `invoice-originals` bucket setup.
- Invoice database record.
- Invoice list page.

Acceptance criteria:

- User can upload a PDF/image within size/page limits.
- Uploaded invoice appears in inbox.
- Unauthorized user cannot access another org invoice or storage object.
- Authorized user can get a short-lived preview URL.

### Milestone 3: Background Processing

Deliverables:

- Redis queue.
- Worker process.
- Mock extraction provider.
- Status transitions.

Acceptance criteria:

- Upload queues a job.
- Worker changes status from `uploaded` to `processing` to `needs_review`.
- Extracted fake data appears on invoice detail page.

### Milestone 4: Review UI

Deliverables:

- Invoice preview.
- Editable extracted fields.
- Save corrections.
- Warnings display.
- Approve button.

Acceptance criteria:

- User can view original invoice and fields side by side.
- User can edit values.
- User can approve invoice.
- Approved invoice appears in approved filter.

### Milestone 5: Real Text Extraction

Deliverables:

- Digital PDF text extraction provider.
- Rule-based parser for MVP fields.
- Normalization logic.
- Field confidence.

Acceptance criteria:

- At least 5 sample digital PDF invoices extract usable values.
- Missing/uncertain fields generate warnings.

### Milestone 6: Export

Deliverables:

- CSV export.
- XLSX export.
- Export jobs.
- Download links.

Acceptance criteria:

- User can export approved invoices.
- Export file opens correctly.
- Amount/date formatting is correct.

### Milestone 7: Billing Limits

Deliverables:

- Usage tracking.
- Plan limits.
- Stripe checkout.
- Stripe webhook handling.
- Organization subscription fields.
- Billing settings page.

Acceptance criteria:

- Free plan limit is enforced.
- Paid plan changes organization limit.
- Stripe webhook updates subscription status.

### Milestone 8: External OCR Provider

Deliverables:

- Provider adapter.
- Configurable provider selection.
- Error handling.
- Retry logic.
- Provider bake-off script that runs the same sample invoice set through multiple adapters.
- Cost, latency, field accuracy, and correction tracking for each provider.

Acceptance criteria:

- Scanned images can be processed.
- Provider failure creates a clear failed state.
- Reprocess action works.
- A documented provider decision exists before public launch.

## 20. Coding Agent Instructions

When implementing this project:

1. Build the smallest complete workflow first: login, upload, process mock data, review, export.
2. Keep OCR provider code behind an interface.
3. Do not hardcode one provider throughout the app.
4. Keep original file storage separate from extracted structured data.
5. Use organization authorization checks on every invoice endpoint.
6. Store money as decimals, not floats.
7. Store dates as date types, not display strings.
8. Always return field confidence and warnings.
9. Never log raw invoice text in production logs.
10. Add tests for every normalization and validation function.

## 21. Suggested Folder Structure

```text
invoice-saas/
  backend/
    app/
      main.py
      core/
        config.py
        security.py
      db/
        session.py
        models.py
        migrations/
      invoices/
        routes.py
        schemas.py
        service.py
        validation.py
        normalization.py
        exports.py
      extraction/
        base.py
        mock_provider.py
        pdf_text_provider.py
        external_provider.py
      storage/
        base.py
        local.py
        supabase_storage.py
      billing/
        routes.py
        stripe_service.py
      workers/
        process_invoice.py
      tests/
    pyproject.toml
    Dockerfile
  frontend/
    app/
      login/
      app/
        invoices/
        suppliers/
        exports/
        settings/
    components/
      invoice-preview.tsx
      invoice-review-form.tsx
      upload-dropzone.tsx
      status-badge.tsx
    lib/
      api.ts
      auth.ts
      formatting.ts
    package.json
    Dockerfile
  supabase/
    rls.sql
    storage-policies.sql
  docker-compose.yml
  README.md
```

## 22. Sample Backend Schemas

### Invoice Response

```json
{
  "id": "6d385704-38cd-4d64-8266-4f3433d57c24",
  "status": "needs_review",
  "original_filename": "invoice.pdf",
  "invoice_number": "FA-2026-001",
  "invoice_date": "2026-06-23",
  "due_date": "2026-07-23",
  "currency": "EUR",
  "subtotal_amount": "1000.00",
  "tax_amount": "200.00",
  "total_amount": "1200.00",
  "supplier": {
    "name": "Example SARL",
    "vat_number": "FR12345678901"
  },
  "confidence": {
    "overall": 0.87,
    "invoice_number": 0.92,
    "total_amount": 0.98
  },
  "warnings": [
    {
      "code": "line_items_not_extracted",
      "severity": "info",
      "message": "Line items were not extracted for this invoice."
    }
  ],
  "file_preview_url": "https://signed-url.example"
}
```

## 23. Launch Checklist

Before first customer test:

- Upload works reliably.
- Review UI is fast enough.
- Export works.
- Duplicate detection exists.
- Failed extraction is recoverable.
- There is a privacy policy.
- There is a clear data deletion path.
- There are sample invoices for demos.
- There is a feedback button or support email.
- Basic analytics track upload, extraction success, review, export.

## 24. Customer Discovery Script

Use this to test the product idea:

1. How many invoices do you process per month?
2. Where do invoices arrive today: email, portal, paper, WhatsApp, shared drive?
3. Who enters invoice data manually?
4. What fields do you absolutely need?
5. What accounting tool do you use?
6. How often are invoice totals or VAT data wrong?
7. Would CSV/XLSX export solve the first version for you?
8. What would make you trust extracted data?
9. What is the cost of a mistake?
10. Would you pay per invoice, per month, or per user?

## 25. Best First Version

The best first version is not a glamorous AI demo. It is a reliable workflow:

```text
Upload invoice -> extract key fields -> review quickly -> approve -> export
```

Everything else should serve that workflow.
