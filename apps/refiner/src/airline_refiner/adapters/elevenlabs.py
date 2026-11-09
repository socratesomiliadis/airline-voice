"""ElevenLabs authenticated Chat Mode WebSocket sessions and prompt REST updates."""

import asyncio
import json
from contextlib import suppress
from typing import Any
from urllib.parse import quote

import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from airline_refiner.adapters.api import request
from airline_refiner.errors import RefinementError
from airline_refiner.models import Simulation

CLIENT_EVENTS = {
    "agent_response",
    "agent_response_correction",
    "agent_response_complete",
    "agent_tool_response",
    "agent_tool_response_full_payload",
    "agent_tool_request",
}


class ElevenLabs:
    def __init__(
        self, client: httpx.AsyncClient, agent_id: str, branch_id: str | None = None
    ) -> None:
        self.client = client
        self.agent_id = agent_id
        self.branch_id = branch_id

    @property
    def agent_path(self) -> str:
        return "convai/agents/" + quote(self.agent_id, safe="")

    @property
    def params(self) -> dict[str, str]:
        return {"branch_id": self.branch_id} if self.branch_id else {}

    async def configure_chat(self) -> str:
        agent = await request(self.client, "GET", self.agent_path, params=self.params)
        if not isinstance(agent, dict):
            raise RefinementError("ElevenLabs returned an invalid agent")
        # Pin subsequent prompt updates and conversations to the same branch.
        self.branch_id = self.branch_id or agent.get("branch_id")
        prompt: str = agent["conversation_config"]["agent"]["prompt"]["prompt"]
        events = set(agent["conversation_config"].get("conversation", {}).get("client_events", []))
        overrides = (agent.get("platform_settings") or {}).get("overrides") or {}
        config_override = overrides.get("conversation_config_override") or {}
        conversation_override = config_override.get("conversation") or {}
        if not CLIENT_EVENTS.issubset(events) or not conversation_override.get("text_only"):
            await request(
                self.client,
                "PATCH",
                self.agent_path,
                params=self.params,
                json={
                    "conversation_config": {
                        "conversation": {
                            "client_events": sorted(events | CLIENT_EVENTS),
                        }
                    },
                    "platform_settings": {
                        "overrides": {
                            **overrides,
                            "conversation_config_override": {
                                **config_override,
                                "conversation": {**conversation_override, "text_only": True},
                            },
                        }
                    },
                },
            )
        return prompt

    async def update_prompt(self, prompt: str) -> None:
        await request(
            self.client,
            "PATCH",
            self.agent_path,
            params=self.params,
            json={"conversation_config": {"agent": {"prompt": {"prompt": prompt}}}},
        )

    async def signed_url(self) -> str:
        result = await request(
            self.client,
            "GET",
            "convai/conversation/get-signed-url",
            params={"agent_id": self.agent_id, **self.params},
        )
        if not isinstance(result, dict) or not isinstance(result.get("signed_url"), str):
            raise RefinementError("ElevenLabs did not return a signed conversation URL")
        return str(result["signed_url"])

    async def transcript(
        self, conversation_id: str, timeout_seconds: float
    ) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    try:
                        result = await request(
                            self.client,
                            "GET",
                            "convai/conversations/" + quote(conversation_id, safe=""),
                        )
                        if isinstance(result, dict) and result.get("status") in {"done", "failed"}:
                            if result["status"] == "failed":
                                raise RefinementError(
                                    "ElevenLabs conversation failed during processing"
                                )
                            transcript = result.get("transcript")
                            if isinstance(transcript, list) and transcript:
                                return transcript
                    except RefinementError as error:
                        if not any(
                            code in str(error) for code in ("HTTP 404", "HTTP 429", "HTTP 503")
                        ):
                            raise
                    await asyncio.sleep(1)
        except TimeoutError:
            raise RefinementError(
                "Timed out retrieving authoritative conversation/tool transcript"
            ) from None

    async def connect(self, result: Simulation) -> "ChatSession":
        url = await self.signed_url()
        socket: ClientConnection | None = None
        try:
            socket = await connect(url, open_timeout=30, max_size=4 * 1024 * 1024)
            await socket.send(
                json.dumps(
                    {
                        "type": "conversation_initiation_client_data",
                        "conversation_config_override": {"conversation": {"text_only": True}},
                    }
                )
            )
            return ChatSession(socket, result)
        except Exception as error:
            if socket is not None:
                with suppress(Exception):
                    await socket.close()
            # A signed URL is a credential: never let a transport exception expose it.
            if isinstance(error, ConnectionClosed) and error.rcvd and error.rcvd.code == 3000:
                raise RefinementError(
                    "ElevenLabs Chat Mode agent is unavailable (close code 3000)"
                ) from None
            raise RefinementError("Unable to establish ElevenLabs Chat Mode session") from None


class ChatSession:
    def __init__(self, socket: ClientConnection, result: Simulation) -> None:
        self.socket = socket
        self.result = result
        self.closed = False
        self.queue: asyncio.Queue[dict[str, Any] | RefinementError | None] = asyncio.Queue()
        # Keep answering provider pings even while the customer LLM is thinking.
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            while True:
                event = json.loads(await self.socket.recv())
                if event.get("type") == "ping":
                    await self.socket.send(
                        json.dumps(
                            {
                                "type": "pong",
                                "event_id": event["ping_event"]["event_id"],
                            }
                        )
                    )
                else:
                    await self.queue.put(event)
        except ConnectionClosed as error:
            if error.rcvd is not None and error.rcvd.code in {1000, 1001}:
                self.closed = True
                await self.queue.put(None)
            else:
                await self.queue.put(
                    RefinementError(
                        "ElevenLabs Chat Mode agent is unavailable (close code 3000)"
                        if error.rcvd and error.rcvd.code == 3000
                        else "ElevenLabs chat connection closed unexpectedly"
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.queue.put(RefinementError("Unable to read ElevenLabs conversation event"))

    async def send(self, text: str) -> None:
        try:
            await self.socket.send(json.dumps({"type": "user_message", "text": text}))
        except ConnectionClosed as error:
            if error.rcvd is not None and error.rcvd.code in {1000, 1001}:
                self.closed = True
                return
            raise RefinementError("Unable to send ElevenLabs customer message") from None
        except Exception:
            raise RefinementError("Unable to send ElevenLabs customer message") from None
        self.result.dialogue.append({"role": "user", "message": text})
        self.result.notify()

    async def receive_turn(self, timeout_seconds: float) -> None:
        """Wait for explicit turn completion; tool preambles are not completed turns."""
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    event = await self.queue.get()
                    if event is None:
                        return
                    if isinstance(event, RefinementError):
                        raise event
                    kind = event.get("type")
                    self.result.events.append(event)
                    if kind == "conversation_initiation_metadata":
                        self.result.conversation_id = event[
                            "conversation_initiation_metadata_event"
                        ]["conversation_id"]
                    elif kind == "agent_response":
                        self.result.dialogue.append(
                            {
                                "role": "agent",
                                "message": event["agent_response_event"]["agent_response"],
                            }
                        )
                    elif kind == "agent_response_correction":
                        correction = event["agent_response_correction_event"][
                            "corrected_agent_response"
                        ]
                        for message in reversed(self.result.dialogue):
                            if message["role"] == "agent":
                                message["message"] = correction
                                break
                    elif kind == "agent_response_complete":
                        self.result.notify()
                        return
                    elif kind in {"agent_tool_response", "agent_tool_response_full_payload"}:
                        tool = event[kind]
                        if (
                            tool.get("tool_name") == "end_call"
                            and tool.get("tool_type") == "system"
                            and tool.get("status") == "success"
                            and tool.get("is_called") is True
                            and not tool.get("is_error")
                            and not tool.get("is_blocked")
                        ):
                            self.closed = True
                    elif kind in {"client_tool_call", "client_error", "error"}:
                        raise RefinementError(f"Unexpected ElevenLabs event: {kind}")
                    self.result.notify()
        except TimeoutError:
            raise RefinementError("ElevenLabs agent turn timed out") from None
        except (ValueError, KeyError, TypeError):
            raise RefinementError("ElevenLabs sent a malformed conversation event") from None

    async def close(self) -> None:
        try:
            await self.socket.close()
        finally:
            self.reader.cancel()
            with suppress(asyncio.CancelledError):
                await self.reader
