"""
API Key authentication for Lapidary.

All protected endpoints require the header:
    X-API-Key: <your-key>
or, for OpenAI-compatible clients:
    Authorization: Bearer <your-key>

Set GEMS_API_KEY in your .env file. If the variable is not set,
the server will refuse to start rather than silently run unprotected.
GEMS_CLIENT_KEYS adds more accepted keys, one per client, as
"name:key,name:key" (roadmap item 10), so a key can be rotated or revoked
for one client without touching the others. Every check returns the name
of the key that matched ("default" for GEMS_API_KEY).
"""
import os
import secrets

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_BEARER = HTTPBearer(auto_error=False)


def _get_configured_key() -> str:
    """Return the configured API key, raising at startup if not set."""
    key = os.environ.get("GEMS_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMS_API_KEY is not set. Add it to your .env file before starting the server.\n"
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return key


def accepted_keys() -> dict[str, str]:
    """Every key the server accepts, mapped to the client name it belongs to."""
    keys = {_get_configured_key(): "default"}
    for entry in os.environ.get("GEMS_CLIENT_KEYS", "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, sep, key = entry.partition(":")
        if sep and name.strip() and key.strip():
            keys[key.strip()] = name.strip()
    return keys


def check_key(presented: str | None) -> str | None:
    """The client name for a presented key, or None when it matches nothing. Constant time per key."""
    if not presented:
        return None
    matched = None
    for key, name in accepted_keys().items():
        if secrets.compare_digest(presented, key):
            matched = name
    return matched


def require_api_key(
    x_api_key: str | None = Security(_API_KEY_HEADER),
    bearer: HTTPAuthorizationCredentials | None = Security(_BEARER),
) -> str:
    """
    FastAPI dependency — call this on any route that should be protected.

    Raises HTTP 401 if the header is missing or the key doesn't match.
    Returns the validated key on success.
    """
    # OpenAI-compatible clients (Open WebUI and others) send the key as a bearer token.
    if not x_api_key and bearer is not None:
        x_api_key = bearer.credentials
    if check_key(x_api_key) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass your key in the X-API-Key header or as a bearer token.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
