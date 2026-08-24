from __future__ import annotations

import json
import os
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edutrust.settings")

import django

django.setup()

from django.test import Client
from django.contrib.auth.hashers import make_password
from django.db import connection


def post_json(client: Client, path: str, data: dict, token: str | None = None):
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.post(path, data=json.dumps(data), content_type="application/json", **headers)


def get_json(client: Client, path: str, token: str | None = None):
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.get(path, **headers)


def register_and_login(client: Client, role: str, email_prefix: str):
    email = f"{email_prefix}-{uuid.uuid4()}@example.com"
    password = "StrongPassword123!"
    res = post_json(client, "/api/v1/auth/register", {"role": role, "full_name": f"{role} User", "email": email, "password": password})
    assert res.status_code == 201, res.content
    login = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": password})
    assert login.status_code == 200, login.content
    return login.json()["data"]


def create_admin(email: str, password: str = "StrongPassword123!"):
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO edutrust.users (full_name, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ["Admin User", email, make_password(password)],
        )
        user_id = cur.fetchone()[0]
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s, 'ADMIN')", [user_id])
    return str(user_id)


def test_health_and_ready():
    client = Client()
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200, ready.content
    assert ready.json()["data"]["status"] == "ready"


def test_parent_registration_login_logout():
    client = Client()
    auth = register_and_login(client, "PARENT", "parent")
    assert "access_token" in auth
    logout = post_json(client, "/api/v1/auth/logout", {}, token=auth["access_token"])
    assert logout.status_code == 200, logout.content


def test_invalid_credentials_security_event():
    client = Client()
    email = f"bad-{uuid.uuid4()}@example.com"
    post_json(client, "/api/v1/auth/register", {"role": "PARENT", "full_name": "Bad User", "email": email, "password": "StrongPassword123!"})
    res = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "wrong-password"})
    assert res.status_code == 401
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='LOGIN_FAILED'")
        assert cur.fetchone()[0] >= 1


def test_rbac_admin_authorization_and_audit_event():
    client = Client()
    parent = register_and_login(client, "PARENT", "rbac-parent")
    denied = get_json(client, "/api/v1/admin/security-events", token=parent["access_token"])
    assert denied.status_code == 403

    admin_email = f"admin-{uuid.uuid4()}@example.com"
    create_admin(admin_email)
    admin_login = post_json(client, "/api/v1/auth/login", {"identifier": admin_email, "password": "StrongPassword123!"})
    assert admin_login.status_code == 200, admin_login.content
    token = admin_login.json()["data"]["access_token"]
    allowed = get_json(client, "/api/v1/admin/security-events", token=token)
    assert allowed.status_code == 200, allowed.content
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 1


def test_student_privacy_access_control():
    client = Client()
    parent_a = register_and_login(client, "PARENT", "privacy-a")
    parent_b = register_and_login(client, "PARENT", "privacy-b")
    create = post_json(client, "/api/v1/students", {"display_name": "Ahmed"}, token=parent_a["access_token"])
    assert create.status_code == 201, create.content
    student_id = create.json()["data"]["id"]
    own = get_json(client, f"/api/v1/students/{student_id}", token=parent_a["access_token"])
    assert own.status_code == 200
    other = get_json(client, f"/api/v1/students/{student_id}", token=parent_b["access_token"])
    assert other.status_code == 403
