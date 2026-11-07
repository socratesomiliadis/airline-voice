"""Separate, stateless structured LLM calls over the Chat Completions REST API."""

import asyncio
import json
from collections.abc import Callable
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ValidationError

from airline_refiner.errors import RefinementError


class Model(Protocol):
    async def generate[T: BaseModel](
        self,
        model: str,
        instruction: str,
        data: dict[str, Any],
        schema: type[T],
        validate: Callable[[T], None] | None = None,
    ) -> T: ...


def strict_schema(value: Any) -> Any:
    """OpenAI requires every object property, including nullable ones, in required."""
    if isinstance(value, list):
        return [strict_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: strict_schema(item) for key, item in value.items() if key != "default"}
    if result.get("type") == "object":
        result["required"] = list(result.get("properties", {}))
        result["additionalProperties"] = False
    return result


class JsonModel:
    def __init__(self, client: httpx.AsyncClient, attempts: int = 3) -> None:
        self.client = client
        self.attempts = attempts

    async def generate[T: BaseModel](
        self,
        model: str,
        instruction: str,
        data: dict[str, Any],
        schema: type[T],
        validate: Callable[[T], None] | None = None,
    ) -> T:
        feedback = ""
        for attempt in range(self.attempts):
            try:
                response = await self.client.post(
                    "chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": instruction},
                            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
                            *([{"role": "user", "content": feedback}] if feedback else []),
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": schema.__name__,
                                "strict": True,
                                "schema": strict_schema(schema.model_json_schema()),
                            },
                        },
                    },
                )
                response.raise_for_status()
                message = response.json()["choices"][0]["message"]
                if message.get("refusal"):
                    raise RefinementError("Model declined the structured generation request")
                result = schema.model_validate_json(message["content"])
                if validate:
                    validate(result)
                return result
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                if status not in {429, 500, 502, 503, 504}:
                    raise RefinementError(f"Model API rejected request (HTTP {status})") from None
                feedback = f"Previous model request failed with HTTP {status}. Try again."
            except httpx.RequestError:
                feedback = "Previous model request failed due to a transport error. Try again."
            except (ValidationError, ValueError, KeyError, TypeError) as error:
                feedback = (
                    f"Output did not satisfy {schema.__name__}: "
                    + (str(error) if type(error) is ValueError else type(error).__name__)
                    + ". Return a corrected JSON object."
                )
            if attempt + 1 < self.attempts:
                await asyncio.sleep(min(2**attempt, 4))
        raise RefinementError(f"Model generation exhausted {self.attempts} attempts: {feedback}")
