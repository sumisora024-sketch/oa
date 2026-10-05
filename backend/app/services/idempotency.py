from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.cache import cache
from app.core.security import decode_access_token
from app.db import SessionLocal
from app.deps import read_auth_token
from app.models import IdempotencyRecord


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
IDEMPOTENCY_TTL_SECONDS = 120
PROCESSING_TTL_MINUTES = 10
COMPLETED_TTL_HOURS = 24


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

    key = key.strip()
    if not key:
        return JSONResponse(status_code=422, content={"detail": "Idempotency-Key must not be empty"})
    key_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()

    actor = actor_key(request)[:128]
    request_path = request.url.path[:384]
    fingerprint = hashlib.sha256(f"{actor}:{method}:{request.url.path}:{key_digest}".encode("utf-8")).hexdigest()
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

    now = datetime.utcnow()
    db = SessionLocal()
    record_id: int | None = None
    try:
        existing = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_key == actor,
                IdempotencyRecord.method == method,
                IdempotencyRecord.path == request_path,
                IdempotencyRecord.idempotency_key == key_digest,
            )
        )
        if existing and existing.expires_at <= now:
            db.delete(existing)
            db.commit()
            existing = None
        if existing:
            cache.delete(cache_key)
            return JSONResponse(status_code=409, content={"detail": "duplicate request ignored"})
        record = IdempotencyRecord(
            actor_key=actor,
            method=method,
            path=request_path,
            idempotency_key=key_digest,
            status="processing",
            expires_at=now + timedelta(minutes=PROCESSING_TTL_MINUTES),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        record_id = record.id
    except IntegrityError:
        db.rollback()
        cache.delete(cache_key)
        return JSONResponse(status_code=409, content={"detail": "duplicate request ignored"})
    finally:
        db.close()

    try:
        response = await call_next(request)
    except Exception:
        _remove_record(record_id)
        cache.delete(cache_key)
        raise

    if response.status_code >= 400:
        _remove_record(record_id)
        cache.delete(cache_key)
    else:
        _complete_record(record_id, response.status_code)
    return response


def _remove_record(record_id: int | None) -> None:
    if not record_id:
        return
    db = SessionLocal()
    try:
        record = db.get(IdempotencyRecord, record_id)
        if record:
            db.delete(record)
            db.commit()
    finally:
        db.close()


def _complete_record(record_id: int | None, status_code: int) -> None:
    if not record_id:
        return
    db = SessionLocal()
    try:
        record = db.get(IdempotencyRecord, record_id)
        if record:
            record.status = "completed"
            record.status_code = status_code
            record.expires_at = datetime.utcnow() + timedelta(hours=COMPLETED_TTL_HOURS)
            db.commit()
    finally:
        db.close()
