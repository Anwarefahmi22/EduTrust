#!/usr/bin/env bash
set -euo pipefail
PG_BIN=${PG_BIN:-/usr/lib/postgresql/17/bin}
PORT=${PGPORT:-55441}
BASE=${PG_BASE:-/tmp/edutrust_test_pg_$(date -u +%Y%m%dT%H%M%SZ)}
DATA="$BASE/data"
SOCK="$BASE/socket"
LOG="$BASE/server.log"
DB=edutrust_test
mkdir -p "$DATA" "$SOCK"
"$PG_BIN/initdb" -D "$DATA" --auth-local=trust --auth-host=trust --no-instructions >/dev/null
"$PG_BIN/pg_ctl" -D "$DATA" -l "$LOG" -o "-k $SOCK -p $PORT -F" start >/dev/null
cleanup(){ "$PG_BIN/pg_ctl" -D "$DATA" stop -m fast >/dev/null 2>&1 || true; }
trap cleanup EXIT
"$PG_BIN/createdb" -h "$SOCK" -p "$PORT" "$DB"
export DATABASE_URL="postgresql://$(whoami)@localhost:${PORT}/${DB}"
export APP_ENV=development
export DEBUG=true
export SECRET_KEY=dev-test-secret
export JWT_SECRET=dev-test-jwt-secret-with-at-least-32-bytes
export MOCK_PAYMENT_PROVIDER_ENABLED=true
export REAL_PAYMENT_ENABLED=false
export REAL_PAYOUT_ENABLED=false
python scripts/run_migrations.py
export PYTHONPATH="$PWD/backend:$PWD"
export DJANGO_SETTINGS_MODULE=edutrust.settings
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
pytest -q tests
