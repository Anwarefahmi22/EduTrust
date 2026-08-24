from __future__ import annotations

from functools import wraps
from .errors import ApiError


def require_roles(*roles: str):
    required = set(roles)
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                raise ApiError("AUTH_REQUIRED", "Authentication is required.", 401)
            if not required.intersection(set(getattr(user, "roles", []))):
                raise ApiError("FORBIDDEN", "You do not have permission to perform this action.", 403)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator
