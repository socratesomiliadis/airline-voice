"""Reload the existing local Uvicorn service or rebuild the existing Compose API.

Invoked by the trusted reload_command after a verified patch (and after rollback).
Never starts a second development server on an occupied port.
"""

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from airline_refiner.adapters.workspace import atomic_write
from airline_refiner.config import Settings
from airline_refiner.errors import RefinementError


def output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def listeners(port: int) -> set[int]:
    result = output(["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"])
    return {int(line) for line in result.splitlines() if line.isdigit()}


def is_api(command: list[str]) -> bool:
    return "airline_api.main:app" in command and any("uvicorn" in part for part in command)


def require_unwatched(commands: list[list[str]]) -> None:
    if any(
        any(arg == "--reload" or arg.startswith("--reload=") for arg in cmd) for cmd in commands
    ):
        raise RefinementError(
            "API auto-reload is enabled. Restart it with make dev-api (without --reload) "
            "before refinement; generated code must be verified before activation."
        )


def check_api() -> None:
    """Check the existing target before any candidate files are written."""
    parsed = urlparse(str(Settings().api_base_url))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RefinementError("Configure reload_command explicitly for a non-local API")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    pids = listeners(port)
    commands = [shlex.split(output(["ps", "-p", str(pid), "-o", "command="])) for pid in pids]
    require_unwatched(commands)
    if pids and any(is_api(cmd) for cmd in commands):
        return
    container = output(["docker", "compose", "ps", "--status", "running", "-q", "api"])
    if container:
        config = output(["docker", "inspect", "--format", "{{json .Config}}", container])
        if not config:
            raise RefinementError("Unable to inspect existing Compose API command")
        data = json.loads(config)
        require_unwatched([data.get("Cmd") or [], data.get("Entrypoint") or []])
        return
    raise RefinementError("No recognized running API; start it with make dev-api first")


def reload_local(port: int, pids: set[int], state: Path) -> None:
    commands = {pid: shlex.split(output(["ps", "-p", str(pid), "-o", "command="])) for pid in pids}
    owned = {pid: command for pid, command in commands.items() if is_api(command)}
    require_unwatched(list(commands.values()))
    if pids and not owned:
        raise RefinementError("API port is occupied by an unrecognized process; reload refused")
    if owned:
        command = next(iter(owned.values()))
        # Save argv before stopping, so rollback can restart after a failed candidate startup.
        atomic_write(state, json.dumps(command))
        for pid in owned:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 20
        while listeners(port):
            if time.monotonic() >= deadline:
                raise RefinementError(
                    "Existing API did not release its port; no new server started"
                )
            time.sleep(0.1)
    elif state.exists():
        command = json.loads(state.read_text())
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise RefinementError("Invalid saved API launch command")
        if not is_api(command):
            raise RefinementError("Saved launch command does not identify the airline API")
        require_unwatched([command])
    else:
        raise RefinementError("No running API to reload; start the development API first")
    if listeners(port):
        raise RefinementError("API port became occupied; no new server started")
    state.parent.mkdir(parents=True, exist_ok=True)
    with (state.parent / "api.log").open("ab") as log:
        try:
            process = subprocess.Popen(
                command,
                cwd=Path.cwd(),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        except OSError:
            raise RefinementError("Unable to restart API; saved launch command retained") from None
    deadline = time.monotonic() + 20
    while not listeners(port):
        if process.poll() is not None:
            raise RefinementError("Restarted API exited; see artifacts/service/api.log")
        if time.monotonic() >= deadline:
            # Stop our own failed start so rollback can safely launch the restored service.
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
            raise RefinementError("Restarted API did not listen before timeout")
        time.sleep(0.1)
    print("Reloaded local airline API")


def reload_api() -> None:
    parsed = urlparse(str(Settings().api_base_url))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RefinementError("Configure reload_command explicitly for a non-local API")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    pids = listeners(port)
    local_api = any(
        is_api(shlex.split(output(["ps", "-p", str(pid), "-o", "command="]))) for pid in pids
    )
    if not local_api and output(["docker", "compose", "ps", "--status", "running", "-q", "api"]):
        # Replaces an existing container; never creates another competing local API.
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--build", "--no-deps", "api"],
            check=False,
        )
        if result.returncode:
            raise RefinementError("Compose API rebuild/reload failed")
        print("Reloaded Compose airline API")
        return
    reload_local(port, pids, Path("artifacts/service/api-command.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check activation safety without reload"
    )
    args = parser.parse_args()
    try:
        if args.check:
            check_api()
        else:
            reload_api()
    except (RefinementError, OSError, ValueError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, RefinementError) else type(error).__name__
        print(message, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
