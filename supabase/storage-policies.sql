-- Supabase Storage bucket policies (§14). Buckets are PRIVATE; access only via
-- signed URLs issued by the FastAPI backend after org/role checks.
-- Apply in the Supabase Studio SQL editor after creating the buckets:
--   invoice-originals, invoice-exports, ocr-raw-results

-- All three buckets must be created as PRIVATE.

-- Service-role (backend) bypasses RLS, so no permissive policies are required
-- for end users. The browser never uses the service-role key.

-- Optional: allow authenticated users to read only objects under their own
-- org path is NOT enough for security because bucket is private; signed URLs
-- issued by the backend are the access path. This file is intentionally a
-- placeholder documenting that backend-issued signed URLs are the strategy.