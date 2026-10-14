from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.modules.search.providers.base import LLMMessage, LLMProvider, LLMResponse, ToolCall

_override_provider: LLMProvider | None = None


def set_llm_provider_for_tests(provider: LLMProvider | None) -> None:
    global _override_provider
    _override_provider = provider


def get_llm_provider() -> LLMProvider | None:
    if _override_provider is not None:
        return _override_provider
    if not settings.ai_enabled or not settings.openai_api_key:
        return None
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_tokens=settings.ai_max_output_tokens,
        timeout=settings.ai_timeout_seconds,
    )


class OpenAIProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int = 1024,
        timeout: float = 30.0,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload = [_to_openai_message(m) for m in messages]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": payload,
            "max_tokens": self._max_tokens,
            "temperature": 0.3,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
            )
        return LLMResponse(content=choice.content, tool_calls=tool_calls)


def _to_openai_message(message: LLMMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content or "",
        }
    data: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in message.tool_calls
        ]
        data["content"] = message.content
    return data
