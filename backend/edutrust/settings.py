from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-unsafe-secret")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-unsafe-jwt-secret")
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "900"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MOCK_PAYMENT_PROVIDER_ENABLED = os.getenv("MOCK_PAYMENT_PROVIDER_ENABLED", "true").lower() == "true"
REAL_PAYMENT_ENABLED = os.getenv("REAL_PAYMENT_ENABLED", "false").lower() == "true"
REAL_PAYOUT_ENABLED = os.getenv("REAL_PAYOUT_ENABLED", "false").lower() == "true"
BOOKING_HOLD_DURATION_SECONDS = int(os.getenv("BOOKING_HOLD_DURATION_SECONDS", "600"))

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "edutrust_api",
]

MIDDLEWARE = [
    "edutrust_api.middleware.RequestIDMiddleware",
    "edutrust_api.middleware.SimpleCORSMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "edutrust_api.middleware.StructuredRequestLogMiddleware",
]

ROOT_URLCONF = "edutrust.urls"
WSGI_APPLICATION = "edutrust.wsgi.application"
ASGI_APPLICATION = "edutrust.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/edutrust_dev")
parsed = urlparse(DATABASE_URL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "OPTIONS": {"options": "-c search_path=edutrust,public"},
    }
}
if parsed.query:
    # Keep simple for DEV; unix socket URLs should be supplied through host query only if needed later.
    pass

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["edutrust_api.auth.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": [],
    "EXCEPTION_HANDLER": "edutrust_api.errors.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "10000/min", "user": "10000/min"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "jsonish": {"format": '{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "jsonish"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
