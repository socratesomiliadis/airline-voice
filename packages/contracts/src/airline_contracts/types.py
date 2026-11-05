"""Transport-neutral payload aliases; domain request schemas are intentionally deferred."""

from pydantic import JsonValue

type JsonObject = dict[str, JsonValue]
