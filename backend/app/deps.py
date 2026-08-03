from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db import get_db
from app.models import User


def read_auth_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    cookie = request.cookies.get("oa_session")
    return cookie or None


def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    token = read_auth_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")

    ttl = get_settings().access_token_expire_minutes * 60
    session = cache.refresh_json(f"session:{payload.get('jti')}", ttl)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已过期")
    response.set_cookie("oa_session", token, httponly=True, samesite="lax", max_age=ttl, secure=False)

    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不可用")
    reset_allowed_paths = {"/api/auth/me", "/api/auth/password/change", "/api/auth/logout"}
    if user.must_reset_password and request.url.path not in reset_allowed_paths:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="首次登录需要重置密码")
    return user
