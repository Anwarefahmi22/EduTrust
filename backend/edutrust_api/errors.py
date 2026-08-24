from __future__ import annotations

import logging
from django.db import IntegrityError, DatabaseError
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response

logger = logging.getLogger("edutrust.errors")

class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

def error_response(request, code: str, message: str, status: int, details: dict | None = None):
    return Response(
        {"error": {"code": code, "message": message, "request_id": getattr(request, "request_id", None), "details": details or {}}},
        status=status,
    )

def exception_handler(exc, context):
    request = context.get("request")
    if isinstance(exc, ApiError):
        return error_response(request, exc.code, exc.message, exc.status_code, exc.details)
    if isinstance(exc, IntegrityError):
        return error_response(request, "CONFLICT", "The requested operation conflicts with existing data or state.", 409)
    if isinstance(exc, DatabaseError):
        logger.exception("Database API exception", exc_info=exc)
        text = str(exc)
        if "is not available" in text or "duplicate key value" in text or "conflicts with existing" in text:
            return error_response(request, "BOOKING_SLOT_UNAVAILABLE", "The selected slot is no longer available.", 409)
        return error_response(request, "DATABASE_ERROR", "A database operation failed.", 500)
    response = drf_exception_handler(exc, context)
    if response is not None:
        code = "VALIDATION_ERROR" if response.status_code == 400 else "API_ERROR"
        if response.status_code == 401:
            code = "AUTH_REQUIRED"
        elif response.status_code == 403:
            code = "FORBIDDEN"
        elif response.status_code == 404:
            code = "RESOURCE_NOT_FOUND"
        return error_response(request, code, "Request failed.", response.status_code, response.data if isinstance(response.data, dict) else {})
    logger.exception("Unhandled API exception", exc_info=exc)
    return error_response(request, "INTERNAL_ERROR", "Internal server error.", 500)
