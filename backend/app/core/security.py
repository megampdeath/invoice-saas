"""Supabase JWT verification.

The frontend sends the Supabase access token as a Bearer token. The backend
verifies the JWT signature against Supabase's published public keys (JWKS),
validates audience and issuer, and maps `sub` to the application users table.

Newer Supabase projects sign JWTs with asymmetric keys (ES256/RS256) exposed at
`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. Older projects used HS256 with
the project JWT secret. We support both, with a dev-only unsigned fallback.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_JWKS_CLIENT = None


def _jwks_url() -> str:
    base = settings.supabase_url.rstrip("/")
    return f"{base}/auth/v1/.well-known/jwks.json"


def _get_jwks_client():
    global _JWKS_CLIENT
    if _JWKS_CLIENT is None:
        _JWKS_CLIENT = jwt.PyJWKClient(_jwks_url())
    return _JWKS_CLIENT


@dataclass
class AuthContext:
    user_id: str
    email: str
    role: str
    raw_token: str


def _decode_token(token: str) -> dict:
    """Decode and validate a Supabase access token.

    Tries asymmetric (JWKS) verification first, then HS256 with the service key,
    then a dev-only unsigned inspection fallback.
    """
    # 1) Asymmetric verification via JWKS (ES256/RS256) — modern Supabase default.
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=settings.supabase_jwt_audience or None,
            issuer=settings.supabase_jwt_issuer or None,
            options={"require": ["exp", "iat", "sub"]},
        )
    except Exception as exc:
        logger.debug("JWKS verification failed: %s", exc)

    # 2) HS256 with the project secret/key — legacy Supabase projects.
    try:
        return jwt.decode(
            token,
            settings.supabase_service_key or settings.supabase_publishable_key,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience or None,
            issuer=settings.supabase_jwt_issuer or None,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.debug("HS256 verification failed: %s", exc)

    # 3) Dev-only unsigned fallback so local dev isn't blocked by key mismatches.
    if not settings.is_dev:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth token",
        )
    return jwt.decode(token, options={"verify_signature": False})


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: no subject")
    return AuthContext(
        user_id=str(sub),
        email=str(payload.get("email") or payload.get("user_email") or ""),
        role=str(payload.get("role") or "authenticated"),
        raw_token=token,
    )


CurrentUser = Depends(get_current_user)