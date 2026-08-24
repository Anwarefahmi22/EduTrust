from __future__ import annotations

from django.db import connection, transaction


def fetchone(sql: str, params: list | tuple | None = None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
        return dict(zip(columns, row))


def fetchall(sql: str, params: list | tuple | None = None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        columns = [col[0] for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def execute(sql: str, params: list | tuple | None = None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.rowcount


def tx():
    return transaction.atomic()
