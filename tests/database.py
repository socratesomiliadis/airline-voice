"""Migration helper for isolated database tests."""

import os
import subprocess
import sys


def migrate(database_url: str, *arguments: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", *arguments],
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
