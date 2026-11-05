"""Application failures mapped to HTTP at the boundary."""

from typing import Any


class BookingError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details
