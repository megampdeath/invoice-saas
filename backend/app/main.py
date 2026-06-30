"""FastAPI application entrypoint."""
from __future__ import annotations

import hmac
import hashlib
import time
import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.core.config import settings
from app.invoices.routes import router as invoices_router
from app.invoices.organizations import router as organizations_router
from app.invoices.suppliers import router as suppliers_router
from app.billing.routes import router as billing_router
from app.storage.supabase_storage import get_storage

app = FastAPI(title="Invoice SaaS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices_router)
app.include_router(organizations_router)
app.include_router(suppliers_router)
app.include_router(billing_router)


@app.get("/")
def root():
    return {"name": "invoice-saas-api", "app_env": settings.app_env}


@app.get("/api/storage/signed")
def storage_signed(bucket: str = Query(...), key: str = Query(...), exp: int = Query(...), sig: str = Query(...)):
    """Local dev signed-URL endpoint (verifies HMAC signature)."""
    if time.time() > exp:
        raise HTTPException(403, "URL expired")
    msg = f"{bucket}/{key}:{exp}".encode()
    expected = hmac.new((settings.preview_token_secret or "dev-secret").encode(), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig or ""):
        raise HTTPException(403, "Invalid signature")
    storage = get_storage() if settings.storage_backend == "supabase" else None
    if storage is None:
        from app.storage.local import LocalStorage
        storage = LocalStorage(settings.local_storage_dir)
    data = storage.get(bucket, key)
    return Response(content=data)