"""
API Key authentication for gemsAPI.

All protected endpoints require the header:
    X-API-Key: <your-key>

Set GEMS_API_KEY in your .env file. If the variable is not set,
the server will refuse to start rather than silently run unprotected.
"""
import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_configured_key() -> str:
    """Return the configured API key, raising at startup if not set."""
    key = os.environ.get("GEMS_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMS_API_KEY is not set. Add it to your .env file before starting the server.\n"
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return key


def require_api_key(x_api_key: str | None = Security(_API_KEY_HEADER)) -> str:
    """
    FastAPI dependency — call this on any route that should be protected.

    Raises HTTP 401 if the header is missing or the key doesn't match.
    Returns the validated key on success.
    """
    expected = _get_configured_key()
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass your key in the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
