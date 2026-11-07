"""Separate, stateless structured LLM calls over Anthropic's Messages REST API."""

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


def anthropic_schema(value: Any) -> Any:
    """Move unsupported constraints into descriptions; Pydantic still enforces them."""
    if isinstance(value, list):
        return [anthropic_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    unsupported = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "maxItems",
        "uniqueItems",
    }
    constraints = {key: item for key, item in value.items() if key in unsupported}
    if value.get("minItems", 0) > 1:
        constraints["minItems"] = value["minItems"]
    result = {key: anthropic_schema(item) for key, item in value.items() if key not in constraints}
    if constraints:
        result["description"] = (
            value.get("description", "") + " Constraints: " + json.dumps(constraints)
        ).strip()
    if result.get("type") == "object":
        result["additionalProperties"] = False
    return result


class JsonModel:
    def __init__(
        self, client: httpx.AsyncClient, attempts: int = 3, max_tokens: int = 16384
    ) -> None:
        self.client = client
        self.attempts = attempts
        self.max_tokens = max_tokens

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
                    "messages",
                    json={
                        "model": model,
                        "max_tokens": self.max_tokens,
                        "system": instruction,
                        "messages": [
                            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
                            *([{"role": "user", "content": feedback}] if feedback else []),
                        ],
                        "output_config": {
                            "format": {
                                "type": "json_schema",
                                "schema": anthropic_schema(schema.model_json_schema()),
                            },
                        },
                    },
                )
                response.raise_for_status()
                message = response.json()
                if message.get("stop_reason") == "refusal":
                    raise RefinementError("Model declined the structured generation request")
                if message.get("stop_reason") == "max_tokens":
                    raise RefinementError(
                        "Model output reached model_max_tokens; increase it in refinement config"
                    )
                if message.get("stop_reason") != "end_turn":
                    raise ValueError("Expected a completed model response")
                content = "".join(
                    block["text"] for block in message["content"] if block["type"] == "text"
                )
                result = schema.model_validate_json(content)
                if validate:
                    validate(result)
                return result
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                if status not in {429, 500, 502, 503, 504, 529}:
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
