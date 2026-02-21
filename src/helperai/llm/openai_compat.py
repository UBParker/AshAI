"""OpenAI-compatible LLM provider. Works with OpenAI, Ollama, vLLM, LM Studio, etc."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from helperai.core.exceptions import LLMError
from helperai.llm.message_types import Message, StreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


class OpenAICompatProvider:
    """Speaks the OpenAI chat/completions API. Works with any compatible endpoint."""

    def __init__(self, name: str, base_url: str, api_key: str = "") -> None:
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @property
    def name(self) -> str:
        return self._name

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def stream(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        body: dict = {
            "model": model,
            "messages": [m.to_openai_dict() for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = [t.to_openai_dict() for t in tools]

        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=body, headers=self._headers()
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    raise LLMError(
                        f"LLM API error {resp.status_code}: {error_body.decode()}"
                    )

                # Accumulate tool call deltas across chunks
                pending_tool_calls: dict[int, dict] = {}  # index → {id, name, arguments}

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        # Emit any accumulated tool calls
                        if pending_tool_calls:
                            tcs = [
                                ToolCall(
                                    id=tc["id"],
                                    name=tc["name"],
                                    arguments=tc["arguments"],
                                )
                                for tc in pending_tool_calls.values()
                            ]
                            yield StreamChunk(tool_calls=tcs, finish_reason="tool_calls")
                            pending_tool_calls.clear()
                        break

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    finish = choice.get("finish_reason")

                    # Text content
                    content = delta.get("content") or ""

                    # Tool call deltas
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            if idx not in pending_tool_calls:
                                pending_tool_calls[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }
                            tc = pending_tool_calls[idx]
                            if "id" in tc_delta:
                                tc["id"] = tc_delta["id"]
                            fn = tc_delta.get("function", {})
                            if "name" in fn:
                                tc["name"] = fn["name"]
                            if "arguments" in fn:
                                tc["arguments"] += fn["arguments"]

                    if finish == "tool_calls" and pending_tool_calls:
                        tcs = [
                            ToolCall(
                                id=tc["id"],
                                name=tc["name"],
                                arguments=tc["arguments"],
                            )
                            for tc in pending_tool_calls.values()
                        ]
                        yield StreamChunk(tool_calls=tcs, finish_reason="tool_calls")
                        pending_tool_calls.clear()
                    elif content:
                        yield StreamChunk(delta_content=content)

                    if finish and finish != "tool_calls":
                        # Flush any remaining tool calls
                        if pending_tool_calls:
                            tcs = [
                                ToolCall(
                                    id=tc["id"],
                                    name=tc["name"],
                                    arguments=tc["arguments"],
                                )
                                for tc in pending_tool_calls.values()
                            ]
                            yield StreamChunk(tool_calls=tcs, finish_reason="tool_calls")
                            pending_tool_calls.clear()
                        yield StreamChunk(finish_reason=finish)

        except httpx.HTTPError as e:
            raise LLMError(f"HTTP error communicating with LLM: {e}") from e

    async def list_models(self) -> list[str]:
        """Fetch available models from the /models endpoint."""
        try:
            resp = await self._client.get("/models", headers=self._headers())
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = data.get("data", [])
            return sorted(m.get("id", "") for m in models if m.get("id"))
        except Exception:
            logger.warning("Failed to list models for provider %s", self._name)
            return []

    async def close(self) -> None:
        await self._client.aclose()
