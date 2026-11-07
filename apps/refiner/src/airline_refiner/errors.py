"""Errors with messages suitable for artifacts and console output."""


class RefinementError(RuntimeError):
    pass


class RecoveryError(RefinementError):
    """Rollback could not restore a known running state; no more runs are safe."""
