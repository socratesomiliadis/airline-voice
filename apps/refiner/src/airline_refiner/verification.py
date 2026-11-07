"""Pytest plugin enforcing required PostgreSQL regressions during code repair."""

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from airline_refiner.adapters.workspace import Artifacts, Workspace, atomic_write
from airline_refiner.config import Settings, load_config
from airline_refiner.errors import RefinementError


@dataclass
class Verification:
    path: Path
    nonce: str
    required: list[str]
    selected: dict[str, bool] = field(default_factory=dict)
    deselected: set[str] = field(default_factory=set)
    outcomes: dict[str, dict[str, str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def matches(self, nodeid: str, pattern: str) -> bool:
        return (
            nodeid == pattern
            or nodeid.startswith(pattern + "::")
            or nodeid.startswith(pattern + "[")
        )

    def required_node(self, nodeid: str) -> bool:
        return any(self.matches(nodeid, pattern) for pattern in self.required)


_verification: Verification | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _verification
    path = os.environ.get("AIRLINE_VERIFICATION_REPORT")
    _verification = (
        Verification(
            path=Path(path),
            nonce=os.environ["AIRLINE_VERIFICATION_NONCE"],
            required=json.loads(os.environ["AIRLINE_REQUIRED_DATABASE_TESTS"]),
        )
        if path
        else None
    )


def pytest_collection_finish(session: pytest.Session) -> None:
    if _verification:
        _verification.selected = {
            item.nodeid: "postgres_url" in getattr(item, "fixturenames", [])
            for item in session.items
            if _verification.required_node(item.nodeid)
        }


def pytest_deselected(items: list[pytest.Item]) -> None:
    if _verification:
        _verification.deselected.update(
            item.nodeid for item in items if _verification.required_node(item.nodeid)
        )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if _verification and report.nodeid in _verification.selected:
        _verification.outcomes.setdefault(report.nodeid, {})[report.when] = report.outcome


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    state = _verification
    if state is None:
        return
    missing = [
        pattern
        for pattern in state.required
        if not any(state.matches(nodeid, pattern) for nodeid in state.selected)
    ]
    incomplete = [
        nodeid
        for nodeid, has_postgres in state.selected.items()
        if not has_postgres
        or any(
            state.outcomes.get(nodeid, {}).get(phase) != "passed"
            for phase in ("setup", "call", "teardown")
        )
    ]
    if missing:
        state.errors.append("Required database tests were not collected: " + ", ".join(missing))
    if state.deselected:
        state.errors.append("Required database tests were deselected")
    if incomplete:
        state.errors.append(
            "Required database tests skipped, failed, or lacked PostgreSQL fixtures"
        )
    report: dict[str, Any] = {
        "nonce": state.nonce,
        "passed": exitstatus == 0 and not state.errors and bool(state.selected),
        "pytest_exit_status": int(exitstatus),
        "required_groups": state.required,
        "collected_nodeids": sorted(state.selected),
        "passed_nodeids": sorted(set(state.selected) - set(incomplete)),
        "incomplete_nodeids": sorted(incomplete),
        "deselected_nodeids": sorted(state.deselected),
        "errors": state.errors,
    }
    atomic_write(state.path, json.dumps(report, indent=2) + "\n")
    if not report["passed"]:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        terminal = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal:
            for error in state.errors:
                terminal.write_line(error, red=True)


def main() -> None:
    settings = Settings()
    config = load_config(settings.config_path)
    artifacts = Artifacts(
        Path("artifacts/backend-verification"), [settings.test_database_url.get_secret_value()]
    )
    try:
        report = asyncio.run(
            Workspace(
                config, test_database_url=settings.test_database_url.get_secret_value()
            ).verify("checks", artifacts)
        )
    except RefinementError as error:
        raise SystemExit(str(error)) from None
    print(f"PostgreSQL verification passed: {len(report['passed_nodeids'])} required tests")


if __name__ == "__main__":
    main()
