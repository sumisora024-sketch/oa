from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy import select

from app.core.security import decode_access_token
from app.db import SessionLocal
from app.deps import read_auth_token
from app.models import AuditLog, User


SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "apikey", "authorization"}
SKIP_PREFIXES = {"/api/auth/login", "/api/auth/password", "/api/settings/mail"}


def is_download_request(request: Request) -> bool:
    path = request.url.path.lower()
    return request.method.upper() == "GET" and (
        path.endswith("/download")
        or path.endswith(".pdf")
        or "/fixed-files/" in path
        or path.endswith("/fixed-files/download-all")
    )


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, child in value.items():
            key_text = str(key).lower()
            if any(sensitive in key_text for sensitive in SENSITIVE_KEYS):
                cleaned[key] = "***"
            else:
                cleaned[key] = sanitize(child)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def infer_module(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]
    return None


def infer_entity_id(path: str) -> str | None:
    for part in reversed([part for part in path.split("/") if part]):
        if part.isdigit():
            return part
    return None


def user_from_request(request: Request) -> User | None:
    token = read_auth_token(request)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except ValueError:
        return None
    db = SessionLocal()
    try:
        return db.scalar(select(User).where(User.id == int(payload["sub"])))
    finally:
        db.close()


async def audit_mutation_request(request: Request, call_next):
    method = request.method.upper()
    path = request.url.path
    download_request = is_download_request(request)
    if (method in {"GET", "HEAD", "OPTIONS"} and not download_request) or any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return await call_next(request)

    payload: Any = None
    content_type = request.headers.get("content-type", "")
    forwarded_request = request
    if "application/json" in content_type:
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body}

        forwarded_request = Request(request.scope, receive)
        if body:
            try:
                payload = sanitize(json.loads(body.decode("utf-8")))
            except json.JSONDecodeError:
                payload = {"raw": "<invalid-json>"}
    elif "multipart/form-data" in content_type:
        payload = {"content_type": "multipart/form-data", "note": "file/form upload payload omitted"}
    elif content_type:
        payload = {"content_type": content_type}

    response = await call_next(forwarded_request)
    if response.status_code >= 400:
        return response

    user = user_from_request(request)
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                user_id=user.id if user else None,
                user_email=user.email if user else None,
                method=method,
                path=path,
                module=infer_module(path),
                action="download" if download_request else method.lower(),
                entity_type=infer_module(path),
                entity_id=infer_entity_id(path),
                after={"request": payload, "status_code": response.status_code},
                ip=request.client.host if request.client else None,
            )
        )
        db.commit()
    finally:
        db.close()
    return response
