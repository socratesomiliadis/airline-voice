"""Disposable PostgreSQL databases shared by integration test modules."""

import asyncio
import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.database import migrate


@pytest.fixture
def postgres_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    database_name = f"airline_test_{uuid4().hex}"

    async def manage_database(create: bool) -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                command = (
                    f'CREATE DATABASE "{database_name}"'
                    if create
                    else f'DROP DATABASE "{database_name}" WITH (FORCE)'
                )
                await connection.execute(text(command))
        finally:
            await engine.dispose()

    asyncio.run(manage_database(create=True))
    database_url = (
        make_url(admin_url).set(database=database_name).render_as_string(hide_password=False)
    )
    try:
        migrate(database_url, "upgrade", "head")
        yield database_url
    finally:
        asyncio.run(manage_database(create=False))
