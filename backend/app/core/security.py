from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, role: str, email: str, expires_minutes: int | None = None) -> tuple[str, str, int]:
    idle_minutes = expires_minutes or settings.access_token_expire_minutes
    expire_at = datetime.now(timezone.utc) + timedelta(days=7)
    jti = str(uuid4())
    payload = {
        "sub": subject,
        "role": role,
        "email": email,
        "jti": jti,
        "exp": expire_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, jti, idle_minutes * 60


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
