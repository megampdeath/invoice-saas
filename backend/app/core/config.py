"""Application settings.

All values come from environment variables (see the project .env).
Secret/backend-only values must never be exposed to the browser.
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_files() -> tuple[str, ...]:
    """Search for .env in CWD then parent dirs (project root may be above backend/)."""
    here = os.getcwd()
    files = []
    for d in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        candidate = os.path.join(d, ".env")
        if os.path.isfile(candidate):
            files.append(candidate)
    return tuple(files) or (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    app_base_url: str = ""
    frontend_base_url: str = "http://localhost:3000"
    backend_base_url: str = "http://localhost:8000"

    # --- Database / Redis ---
    database_url: str = ""
    direct_database_url: str = ""
    redis_url: str = ""

    # --- Supabase ---
    next_public_supabase_url: str = ""
    next_public_supabase_publishable_key: str = ""
    supabase_url: str = ""
    # The .env uses SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY. The planning
    # doc uses SUPABASE_SECRET_KEY + publishable key. Support both alias sets.
    supabase_anon_key: str = ""
    supabase_secret_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"

    # --- Storage ---
    storage_backend: str = "supabase"  # 'supabase' or 'local'
    local_storage_dir: str = "./storage"
    supabase_storage_originals_bucket: str = "invoice-originals"
    supabase_storage_exports_bucket: str = "invoice-exports"
    supabase_storage_ocr_raw_bucket: str = "ocr-raw-results"

    # --- Extraction ---
    extraction_provider: str = "mock"  # mock | pdf_text | textract | mindee | ...
    ocr_provider_api_key: str = ""
    mindee_api_key: str = ""

    # --- AWS Textract ---
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # --- Google Document AI ---
    google_application_credentials: str = ""
    google_document_ai_project_id: str = ""
    google_document_ai_location: str = ""
    google_document_ai_processor_id: str = ""

    # --- Azure Document Intelligence ---
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""

    # --- Stripe ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_monthly: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_business_monthly: str = ""

    # --- Misc security ---
    preview_token_secret: str = ""

    # --- Computed helpers (not env) ---
    @property
    def supabase_publishable_key(self) -> str:
        return self.next_public_supabase_publishable_key or self.supabase_anon_key

    @property
    def supabase_service_key(self) -> str:
        return self.supabase_service_role_key or self.supabase_secret_key

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "dev", "local", "preprod")

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url or self.direct_database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()