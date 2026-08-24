from __future__ import annotations

import json
from django.core.serializers.json import DjangoJSONEncoder

from .db import execute


def write_event(event_type: str, entity_type: str, entity_id: str | None = None, actor_user_id: str | None = None, actor_role: str | None = None, request_id: str | None = None, metadata: dict | None = None):
    execute(
        """
        INSERT INTO edutrust.event_ledger (actor_user_id, actor_role, event_type, entity_type, entity_id, request_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        [actor_user_id, actor_role, event_type, entity_type, entity_id, request_id, json.dumps(metadata or {}, cls=DjangoJSONEncoder)],
    )


def write_security_event(event_type: str, user_id: str | None = None, severity: int = 1, metadata: dict | None = None):
    execute(
        """
        INSERT INTO edutrust.security_events (user_id, event_type, severity, metadata)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        [user_id, event_type, severity, json.dumps(metadata or {}, cls=DjangoJSONEncoder)],
    )
