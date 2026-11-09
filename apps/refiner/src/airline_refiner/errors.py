"""Errors with messages suitable for artifacts and console output."""


class RefinementError(RuntimeError):
    pass


class ApplicationError(RefinementError):
    """A repeatable endpoint failure while independent readiness probes succeed."""

    def __init__(self, method: str, path: str, status: int) -> None:
        self.method, self.path, self.status = method, path, status
        super().__init__(
            f"{method} {path} failed twice (HTTP {status}); health and inventory probes passed"
        )


class RecoveryError(RefinementError):
    """Rollback could not restore a known running state; no more runs are safe."""
