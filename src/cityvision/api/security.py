from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from cityvision.settings import get_settings

_PBKDF_ROUNDS = 120_000


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt_b = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_b, _PBKDF_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF_ROUNDS}${base64.b64encode(salt_b).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds_s, salt_b64, hash_b64 = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(hash_b64.encode())
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def create_access_token(username: str, role: str, expires_minutes: int = 60 * 12) -> str:
    import jwt

    settings = get_settings()
    secret = settings.jwt_secret
    if not secret:
        raise RuntimeError("CITYVISION_JWT_SECRET is not set")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    import jwt

    settings = get_settings()
    if not settings.jwt_secret:
        return None
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None


def actor_from_request_headers(authorization: Optional[str], x_api_key: Optional[str]) -> str:
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            payload = decode_access_token(parts[1].strip())
            if payload and payload.get("sub"):
                return str(payload["sub"])
    settings = get_settings()
    if settings.api_key and x_api_key == settings.api_key:
        return "api_key"
    return "anonymous"
