import hashlib
from datetime import datetime, timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db import get_db
from app.deps import get_current_user, read_auth_token
from app.models import Employee, PasswordResetToken, User
from app.schemas import LoginIn, PasswordChangeIn, PasswordResetConfirm, PasswordResetRequest, TeamsSsoIn, TokenOut, UserOut
from app.services.mail import send_mail

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    settings = get_settings()
    email = payload.email.strip()
    if email.lower() == "admin":
        email = settings.app_admin_email
    user = db.scalar(select(User).where(or_(User.email == email, User.login_id == email, User.login_id == email.upper())))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已停用")

    token, jti, ttl = create_access_token(str(user.id), user.role, user.email)
    cache.set_json(
        f"session:{jti}",
        {"user_id": user.id, "role": user.role, "email": user.email},
        ttl,
    )
    response.set_cookie(
        "oa_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=ttl,
        secure=False,
    )
    return TokenOut(access_token=token, expires_in=ttl, user=UserOut.model_validate(user))


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = read_auth_token(request)
    if token:
        try:
            from app.core.security import decode_access_token

            payload = decode_access_token(token)
            cache.delete(f"session:{payload.get('jti')}")
        except ValueError:
            pass
    response.delete_cookie("oa_session")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/password/reset-request")
def reset_request(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.password_reset_email_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="パスワード再設定メールは現在無効です")
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        return {"ok": True}

    raw_token = token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
    )
    db.commit()
    link = f"{settings.frontend_url}/reset-password?token={raw_token}"
    send_mail(user.email, "OA 密码重置", f"请在 30 分钟内打开链接重置密码：{link}")
    return {"ok": True, "reset_link": link if settings.environment == "development" else None}


@router.post("/password/reset-confirm")
def reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.password_reset_email_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="パスワード再設定メールは現在無効です")
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if not token or token.used_at or token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期")
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户不存在")
    user.password_hash = get_password_hash(payload.new_password)
    user.must_reset_password = False
    token.used_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/password/change", response_model=UserOut)
def change_password(payload: PasswordChangeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserOut:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    user.password_hash = get_password_hash(payload.new_password)
    user.must_reset_password = False
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/sso/teams-placeholder", response_model=TokenOut)
def teams_placeholder(payload: TeamsSsoIn, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    employee = db.scalar(select(Employee).where(Employee.email == payload.email))
    user = db.scalar(select(User).where(User.email == payload.email))
    if not employee:
        employee = Employee(
            full_name=payload.full_name or payload.email.split("@")[0],
            email=payload.email,
            phone="SSO",
            graduation_status="未填写",
            residence="未填写",
            nearest_station="未填写",
            employee_type="一般社員",
        )
        db.add(employee)
        db.flush()
    if not user:
        user = User(
            email=payload.email,
            full_name=payload.full_name or employee.full_name,
            role="employee",
            password_hash=get_password_hash(token_urlsafe(24)),
            must_reset_password=False,
            employee_id=employee.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token, jti, ttl = create_access_token(str(user.id), user.role, user.email)
    cache.set_json(f"session:{jti}", {"user_id": user.id, "role": user.role, "email": user.email}, ttl)
    response.set_cookie("oa_session", token, httponly=True, samesite="lax", max_age=ttl, secure=False)
    return TokenOut(access_token=token, expires_in=ttl, user=UserOut.model_validate(user))
