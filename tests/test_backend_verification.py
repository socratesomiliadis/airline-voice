"""Real subprocess tests of the mandatory PostgreSQL verification receipt."""

import asyncio
import json
import sys

import pytest
from airline_refiner.adapters.workspace import Artifacts, Workspace
from airline_refiner.config import RefinementConfig
from airline_refiner.errors import RefinementError


def workspace(tmp_path, mode):
    source = """import pytest
@pytest.fixture
def postgres_url():
    return 'isolated-plugin-test'
def test_database(postgres_url):
    assert postgres_url
"""
    if mode == "skip":
        source = source.replace("assert postgres_url", "pytest.skip('required test skipped')")
    if mode == "xfail":
        source = source.replace("assert postgres_url", "pytest.xfail('required test xfailed')")
    if mode == "no_fixture":
        source = source.replace("def test_database(postgres_url):", "def test_database():").replace(
            "assert postgres_url", "assert True"
        )
    (tmp_path / "test_database.py").write_text(source)
    command = [sys.executable, "-m", "pytest", "-q", "test_database.py"]
    if mode == "deselect":
        command += ["--deselect=test_database.py::test_database"]
    if mode == "omitted":
        command = [sys.executable, "-c", "pass"]
    config = RefinementConfig(
        workspace_root=tmp_path,
        editable_roots=["backend"],
        verification_command=command,
        required_database_tests=["test_database.py"],
    )
    if mode == "missing_group":
        config.required_database_tests.append("missing.py")
    return Workspace(config, test_database_url="postgresql+asyncpg://test:test@localhost/test")


def test_receipt_is_required_even_when_command_succeeds(tmp_path):
    current = workspace(tmp_path, "omitted")
    with pytest.raises(RefinementError, match="receipt"):
        asyncio.run(current.verify("iteration", Artifacts(tmp_path / "artifacts")))


@pytest.mark.parametrize("mode", ["skip", "xfail", "deselect", "no_fixture", "missing_group"])
def test_skipped_or_missing_required_database_checks_fail_verification(tmp_path, mode):
    current = workspace(tmp_path, mode)
    with pytest.raises(RefinementError, match="exited"):
        asyncio.run(current.verify("iteration", Artifacts(tmp_path / "artifacts")))
    receipt = json.loads((tmp_path / "artifacts/iteration/verification.json").read_text())
    assert not receipt["passed"] and receipt["errors"]


def test_required_database_fixture_must_complete_setup_call_and_teardown(tmp_path):
    current = workspace(tmp_path, "pass")
    receipt = asyncio.run(current.verify("iteration", Artifacts(tmp_path / "artifacts")))
    assert receipt["passed"]
    assert receipt["passed_nodeids"] == ["test_database.py::test_database"]
    assert receipt["nonce"]


def test_missing_database_configuration_fails_before_running_any_command(tmp_path, monkeypatch):
    current = workspace(tmp_path, "pass")
    current.test_database_url = ""

    async def forbidden(*args, **kwargs):
        pytest.fail("No command may run without database configuration")

    monkeypatch.setattr(current, "command", forbidden)
    with pytest.raises(RefinementError, match="TEST_DATABASE_URL"):
        asyncio.run(current.verify("iteration", Artifacts(tmp_path / "artifacts")))
