from __future__ import annotations

import hashlib

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.cache import cache
from app.core.security import decode_access_token
from app.deps import read_auth_token


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
IDEMPOTENCY_TTL_SECONDS = 120


def actor_key(request: Request) -> str:
    token = read_auth_token(request)
    if not token:
        return request.client.host if request.client else "anonymous"
    try:
        payload = decode_access_token(token)
        return str(payload.get("sub") or payload.get("email") or "anonymous")
    except ValueError:
        return "anonymous"


async def reject_duplicate_mutation(request: Request, call_next):
    method = request.method.upper()
    key = request.headers.get("idempotency-key")
    if method not in UNSAFE_METHODS or not key:
        return await call_next(request)

    fingerprint = hashlib.sha256(
        f"{actor_key(request)}:{method}:{request.url.path}:{key}".encode("utf-8")
    ).hexdigest()
    cache_key = f"idempotency:{fingerprint}"
    reserved = cache.add_json_if_absent(
        cache_key,
        {"path": request.url.path, "method": method},
        IDEMPOTENCY_TTL_SECONDS,
    )
    if not reserved:
        return JSONResponse(
            status_code=409,
            content={"detail": "duplicate request ignored"},
        )
    response = await call_next(request)
    if response.status_code >= 400:
        cache.delete(cache_key)
    return response
