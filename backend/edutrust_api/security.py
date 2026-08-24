from __future__ import annotations

import hashlib
import secrets
from django.contrib.auth.hashers import make_password, check_password


def hash_password(raw: str) -> str:
    return make_password(raw)


def verify_password(raw: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    return check_password(raw, encoded)


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
