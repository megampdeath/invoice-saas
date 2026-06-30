"""Vercel Python serverless entry point (catch-all ASGI).

Vercel's Python runtime detects an ASGI `app` object and serves it. This file
mounts the full FastAPI application so every route (/api/health, /api/invoices,
...) is handled. vercel.json rewrites all paths to this catch-all function.
"""
from app.main import app  # noqa: F401  (ASGI app exported for Vercel)
