#!/usr/bin/env bash
# Starts an isolated temporary PostgreSQL cluster and prints DATABASE_URL.
set -euo pipefail
PG_BIN=${PG_BIN:-/usr/lib/postgresql/17/bin}
PORT=${PGPORT:-55440}
BASE=${PG_BASE:-/tmp/edutrust_pg_$(date -u +%Y%m%dT%H%M%SZ)}
DATA="$BASE/data"
SOCK="$BASE/socket"
LOG="$BASE/server.log"
DB=${PGDATABASE:-edutrust_dev}
mkdir -p "$DATA" "$SOCK"
"$PG_BIN/initdb" -D "$DATA" --auth-local=trust --auth-host=trust --no-instructions >/dev/null
"$PG_BIN/pg_ctl" -D "$DATA" -l "$LOG" -o "-k $SOCK -p $PORT -F" start >/dev/null
"$PG_BIN/createdb" -h "$SOCK" -p "$PORT" "$DB"
echo "export DATABASE_URL=postgresql://$(whoami)@localhost:${PORT}/${DB}"
echo "export PGHOST=$SOCK"
echo "export PGPORT=$PORT"
echo "export PGDATA=$DATA"
echo "# Stop with: $PG_BIN/pg_ctl -D $DATA stop -m fast"
