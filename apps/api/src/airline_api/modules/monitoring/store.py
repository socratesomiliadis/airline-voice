"""Read-only artifact access; the API never controls or writes to the worker."""

import re
from pathlib import Path

from airline_contracts.monitoring import MonitoringSnapshot, RunObservation, RunSummary
from pydantic import ValidationError

RUN_ID_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$"


class ObservationStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.cache: dict[str, tuple[int, int, RunObservation]] = {}

    def snapshot(self, run_id: str | None = None) -> MonitoringSnapshot:
        observations = []
        if self.root.is_dir():
            for directory in self.root.iterdir():
                if directory.is_symlink() or not re.fullmatch(RUN_ID_PATTERN, directory.name):
                    continue
                path = directory / "monitor.json"
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    stat = path.stat()
                    if stat.st_size > 10 * 1024 * 1024:
                        continue
                    cached = self.cache.get(directory.name)
                    if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
                        observation = cached[2]
                    else:
                        observation = RunObservation.model_validate_json(path.read_text())
                        if observation.run_id != directory.name:
                            continue
                        self.cache[directory.name] = (stat.st_mtime_ns, stat.st_size, observation)
                    observations.append(observation)
                except (OSError, ValidationError, UnicodeError):
                    continue  # Incomplete or incompatible artifacts cannot break the live stream.
        observations.sort(key=lambda item: item.started_at, reverse=True)
        observations = observations[:100]
        selected = next((item for item in observations if item.run_id == run_id), None)
        if run_id is not None and selected is None:
            raise FileNotFoundError(run_id)
        if selected is None and observations:
            selected = observations[0]
        available = {observation.run_id for observation in observations}
        self.cache = {key: value for key, value in self.cache.items() if key in available}
        return MonitoringSnapshot(
            runs=[RunSummary.model_validate(item.model_dump()) for item in observations],
            run=selected,
        )
