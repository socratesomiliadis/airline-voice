"""Bounded exact-text patches with verification, service reload, and rollback."""

import asyncio
import difflib
import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from airline_refiner.config import RefinementConfig
from airline_refiner.errors import RefinementError
from airline_refiner.models import CodeFault, FileEdit
from airline_refiner.patching import function_bounds, validate_function_changes


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".refiner-tmp")
    try:
        temporary.write_text(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Artifacts:
    def __init__(self, directory: Path, secrets: list[str] | None = None) -> None:
        self.directory = directory
        self.secrets = [secret for secret in (secrets or []) if secret]
        directory.mkdir(parents=True, exist_ok=True)

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        return text

    def write(self, name: str, data: Any) -> None:
        self.write_text(name, json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")

    def write_text(self, name: str, content: str) -> None:
        atomic_write(self.directory / name, self.redact(content))


class Workspace:
    def __init__(self, config: RefinementConfig) -> None:
        self.config = config
        self.root = config.workspace_root.resolve()
        self.roots = [self.root / name for name in config.editable_roots]
        for root in self.roots:
            if not root.resolve().is_relative_to(self.root) or root.is_symlink():
                raise RefinementError(
                    "Editable roots must be real directories inside the workspace"
                )

    @contextmanager
    def lock(self) -> Iterator[None]:
        with (self.root / ".refinement.lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RefinementError(
                    "Another refinement run is already using this workspace"
                ) from None
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def source(self) -> dict[str, str]:
        sources = {}
        for root in self.roots:
            for path in sorted(root.rglob("*.py")):
                self.validate_path(str(path.relative_to(self.root)))
                sources[str(path.relative_to(self.root))] = path.read_text()
        if not sources:
            raise RefinementError("No editable backend source files found")
        if sum(len(text) for text in sources.values()) > self.config.max_source_chars:
            raise RefinementError("Source context exceeds max_source_chars; narrow editable_roots")
        return sources

    def validate_path(self, name: str) -> Path:
        relative = Path(name)
        path = self.root / relative
        if relative.is_absolute() or ".." in relative.parts or path.suffix != ".py":
            raise RefinementError("Code patches require workspace-relative Python paths")
        if any(part.startswith(".") for part in relative.parts):
            raise RefinementError("Code patches cannot modify hidden paths")
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise RefinementError("Code patches cannot traverse symlinks")
        if not any(path.resolve().is_relative_to(root.resolve()) for root in self.roots):
            raise RefinementError("Code patch is outside editable_roots")
        return path

    def plan(
        self, edits: list[FileEdit], sources: dict[str, str], code_faults: list[CodeFault]
    ) -> "PatchTransaction":
        if len({edit.path for edit in edits}) > self.config.max_patch_files:
            raise RefinementError("Code patch exceeds max_patch_files")
        originals: dict[Path, str] = {}
        candidates: dict[Path, str] = {}
        targets = {(fault.path, fault.function) for fault in code_faults}
        changed_functions: dict[Path, set[str]] = {}
        for edit in edits:
            path = self.validate_path(edit.path)
            if (edit.path, edit.function) not in targets:
                raise RefinementError("Patch must target a diagnosed file and function")
            if path not in originals:
                if not path.is_file() or edit.path not in sources:
                    raise RefinementError("Code patches must modify existing source files")
                original = path.read_text()
                if original != sources.get(edit.path):
                    raise RefinementError(
                        "Source changed during repair generation; refusing stale patch"
                    )
                originals[path] = original
                candidates[path] = original
            current = candidates[path]
            try:
                start, end = function_bounds(current, edit.function)
                function_source = current[start:end]
                if function_source.count(edit.old_text) != 1:
                    raise ValueError(
                        "Patch old_text must match exactly once inside the diagnosed function"
                    )
                candidates[path] = (
                    current[:start]
                    + function_source.replace(edit.old_text, edit.new_text, 1)
                    + current[end:]
                )
                compile(candidates[path], str(path), "exec")
            except (SyntaxError, ValueError) as error:
                message = (
                    str(error) if type(error) is ValueError else "Patch contains invalid Python"
                )
                raise RefinementError(message) from None
            changed_functions.setdefault(path, set()).add(edit.function)
        if edits and all(candidates[path] == originals[path] for path in candidates):
            raise RefinementError("Generated code patch makes no change")
        size = sum(len(content) for content in sources.values()) + sum(
            len(content) - len(originals[path]) for path, content in candidates.items()
        )
        if size > self.config.max_source_chars:
            raise RefinementError("Generated code patch exceeds max_source_chars")
        for path, content in candidates.items():
            try:
                validate_function_changes(originals[path], content, changed_functions[path])
            except (SyntaxError, ValueError):
                raise RefinementError(
                    "Patch must preserve code outside the diagnosed functions"
                ) from None
        return PatchTransaction(originals, candidates)

    async def command(self, command: list[str], log: Path, artifacts: Artifacts) -> None:
        """Only trusted configuration supplies argv; generated code supplies no shell commands."""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except OSError:
            raise RefinementError(f"Cannot execute configured command: {command[0]}") from None
        try:
            output, _ = await asyncio.wait_for(
                process.communicate(), timeout=self.config.command_timeout_seconds
            )
        except (TimeoutError, asyncio.CancelledError):
            import signal

            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.communicate()
            raise RefinementError(
                f"Configured command timed out or was cancelled: {command[0]}"
            ) from None
        artifacts.write_text(str(log), output.decode(errors="replace"))
        if process.returncode != 0:
            raise RefinementError(f"Configured command exited {process.returncode}; see {log}")

    async def check_service(self, artifacts: Artifacts) -> None:
        if "airline_refiner.reload_service" in self.config.reload_command:
            await self.command(
                [*self.config.reload_command, "--check"], Path("service-check.log"), artifacts
            )


class PatchTransaction:
    def __init__(self, originals: dict[Path, str], candidates: dict[Path, str]) -> None:
        self.originals = originals
        self.candidates = candidates

    def diff(self, root: Path) -> str:
        return "".join(
            "".join(
                difflib.unified_diff(
                    self.originals[path].splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile="a/" + str(path.relative_to(root)),
                    tofile="b/" + str(path.relative_to(root)),
                )
            )
            for path, content in self.candidates.items()
        )

    def apply(self) -> None:
        try:
            for path, content in self.candidates.items():
                atomic_write(path, content)
        except BaseException:
            self.rollback()
            raise

    def rollback(self) -> None:
        for path, original in self.originals.items():
            atomic_write(path, original)
