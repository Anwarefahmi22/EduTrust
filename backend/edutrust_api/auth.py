from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

import jwt
from django.conf import settings
from django.utils import timezone as dj_timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .db import fetchone

@dataclass
class Principal:
    id: str
    roles: list[str]
    session_id: str | None = None
    is_authenticated: bool = True

    @property
    def pk(self):
        return self.id

    @property
    def is_anonymous(self):
        return False


def make_access_token(user_id: str, roles: list[str], session_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "roles": roles,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.JWT_ACCESS_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationFailed("TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationFailed("INVALID_TOKEN") from exc

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        token = header.removeprefix("Bearer ").strip()
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not user_id or not session_id:
            raise AuthenticationFailed("INVALID_TOKEN")
        session = fetchone(
            """
            SELECT id, revoked_at, expires_at
            FROM edutrust.auth_sessions
            WHERE id = %s AND user_id = %s
            """,
            [session_id, user_id],
        )
        if not session or session["revoked_at"] is not None or session["expires_at"] <= dj_timezone.now():
            raise AuthenticationFailed("SESSION_REVOKED")
        principal = Principal(id=user_id, roles=list(payload.get("roles") or []), session_id=session_id)
        return (principal, token)
