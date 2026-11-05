"""A consistent, explicit response for routes reserved by this scaffold."""

from typing import NoReturn

from fastapi import HTTPException, status


def not_implemented(feature: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "not_implemented", "feature": feature},
    )
