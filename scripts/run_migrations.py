#!/usr/bin/env python3
"""Run the approved EduTrust DEV migration chain.

This runner intentionally executes the checked-in SQL files in order. It does
not generate or alter migrations.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = [
    "database/migrations/001_edutrust_schema_v1.sql",
    "database/migrations/002_edutrust_schema_patch_v1_1.sql",
    "database/migrations/003_edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql",
    "database/migrations/004_edutrust_schema_patch_v1_3.sql",
    "database/migrations/005_edutrust_schema_patch_v1_4.sql",
]


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    for rel in MIGRATIONS:
        path = ROOT / rel
        if not path.exists():
            print(f"Missing migration file: {path}", file=sys.stderr)
            return 3
    for rel in MIGRATIONS:
        path = ROOT / rel
        print(f"Applying {rel} ...", flush=True)
        result = subprocess.run(["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", str(path)], text=True)
        if result.returncode != 0:
            print(f"Migration failed: {rel}", file=sys.stderr)
            return result.returncode
    print("Migration chain complete.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
