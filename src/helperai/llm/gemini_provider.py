"""Google Gemini LLM provider.

Speaks the Gemini REST API directly or through the multi-provider proxy at
/gemini/*.  Auth is handled via ``?key=`` query-param (or delegated to the
proxy which injects the param from GEMINI_API_KEY env).

Streaming uses ``?alt=sse``, which yields newline-delimited ``data: <JSON>``
chunks — not the OpenAI format, so this provider cannot reuse OpenAICompatProvider.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

import httpx

from helperai.core.exceptions import LLMError
from helperai.llm.message_types import Message, StreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Google Gemini provider using the REST API (direct or via proxy)."""

    def __init__(
        self,
        name: str = "gemini",
        base_url: str = "https://generativelanguage.googleapis.com",
        api_key: str = "",
    ) -> None:
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @property
    def name(self) -> str:
        return self._name

    # ── Message conversion ────────────────────────────────────────────────

    @staticmethod
    def _build_contents(
        messages: list[Message],
    ) -> tuple[str, list[dict]]:
        """Convert internal Message list to Gemini ``contents`` format.

        Returns ``(system_instruction_text, contents_list)``.
        Gemini uses roles ``"user"`` / ``"model"`` (not ``"assistant"``).
        """
        system_instruction = ""
        contents: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
                continue

            if msg.role == "tool":
                # Tool results → functionResponse block sent as role=user
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": "tool_result",
                                    "response": {"content": msg.content},
                                }
                            }
                        ],
                    }
                )
                continue

            if msg.role == "assistant":
                parts: list[dict] = []
                if msg.content:
                    parts.append({"text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.arguments) if tc.arguments else {}
                        except json.JSONDecodeError:
                            args = {}
                        parts.append(
                            {"functionCall": {"name": tc.name, "args": args}}
                        )
                if not parts:
                    parts = [{"text": ""}]
                contents.append({"role": "model", "parts": parts})
                continue

            # role == "user"
            contents.append({"role": "user", "parts": [{"text": msg.content}]})

        return system_instruction, contents

    @staticmethod
    def _build_tools(tools: list[ToolDefinition]) -> list[dict]:
        """Convert ToolDefinition list to Gemini ``tools`` format."""
        declarations = [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in tools
            if t.tool_type == "function"
        ]
        return [{"functionDeclarations": declarations}] if declarations else []

    def _params(self, extra: dict | None = None) -> dict:
        """Build query-params dict, injecting ``?key=`` when we have a real key."""
        params: dict = {}
        # "proxy" is a sentinel meaning the upstream proxy handles auth
        if self._api_key and self._api_key != "proxy":
            params["key"] = self._api_key
        if extra:
            params.update(extra)
        return params

    # ── Streaming ─────────────────────────────────────────────────────────

    async def stream(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        system_instruction, contents = self._build_contents(messages)

        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            gemini_tools = self._build_tools(tools)
            if gemini_tools:
                body["tools"] = gemini_tools

        url = f"{self._base_url}/v1beta/models/{model}:streamGenerateContent"
        params = self._params({"alt": "sse"})

        try:
            async with self._client.stream(
                "POST",
                url,
                json=body,
                params=params,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    raise LLMError(
                        f"Gemini API error {resp.status_code}: {error_body.decode()}"
                    )

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        logger.debug("Skipping non-JSON SSE line: %s", data[:80])
                        continue

                    candidates = chunk.get("candidates", [])
                    if not candidates:
                        continue

                    candidate = candidates[0]
                    finish_reason = candidate.get("finishReason", "")
                    content_block = candidate.get("content", {})
                    parts = content_block.get("parts", [])

                    tool_calls: list[ToolCall] = []
                    for part in parts:
                        if "text" in part and part["text"]:
                            yield StreamChunk(delta_content=part["text"])
                        elif "functionCall" in part:
                            fc = part["functionCall"]
                            tool_calls.append(
                                ToolCall(
                                    id=str(uuid.uuid4()),
                                    name=fc.get("name", ""),
                                    arguments=json.dumps(fc.get("args", {})),
                                )
                            )

                    if tool_calls:
                        yield StreamChunk(
                            tool_calls=tool_calls, finish_reason="tool_calls"
                        )
                    elif finish_reason in ("STOP", "MAX_TOKENS"):
                        yield StreamChunk(finish_reason="stop")

        except httpx.HTTPError as e:
            raise LLMError(f"HTTP error communicating with Gemini: {e}") from e

    # ── Housekeeping ──────────────────────────────────────────────────────

    async def list_models(self) -> list[str]:
        return [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

    async def close(self) -> None:
        await self._client.aclose()
