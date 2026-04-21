import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
MONITORING_TOKEN_EXPIRE_HOURS = 1
MONITORING_API_KEY = os.getenv("MONITORING_API_KEY", "monitoring-key-123")


class AuthError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "role": role,
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_monitoring_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=MONITORING_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "role": role,
        "token_type": "monitoring",
        "scope": "monitoring:read",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise AuthError("Invalid or expired token") from exc
