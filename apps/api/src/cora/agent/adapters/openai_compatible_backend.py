"""OpenAI-compatible serving backend for `LocalLLM`.

Talks the `/v1/chat/completions` shape that vLLM, Ollama, llama.cpp, and
other in-house engines expose, so one adapter serves any of them. It is
the production `LocalCompletionBackend`: `LocalLLM` drives it and meters
the GPU time; this class owns the HTTP call and the translation from the
OpenAI wire shape to `LocalCompletion`.

## Structured output

Consumers require a schema-valid `parsed` Decision. This backend asks for
it with `response_format={"type": "json_schema", ...}`, the OpenAI-standard
guided-decoding request that vLLM and llama.cpp honor and recent Ollama
accepts on its `/v1` surface. The model's reply arrives as a JSON string in
`choices[0].message.content`; the backend parses it into `parsed`. If the
server could not honor the schema and returned non-JSON, `parsed` is `None`
and `LocalLLM` raises `LLMSchemaValidationError`, the same contract
`AnthropicLLM` presents from forced tool-use. An engine that wants a
different guided-decoding shape is a construction-time swap, not a change
here.

## Errors

Transport failures are translated to the `LLM` taxonomy so consumers depend
only on the port-level error classes: timeouts to `LLMTimeoutError`, 429 to
`LLMRateLimitError`, 5xx and connection errors to `LLMServerError`, and
other 4xx to `LLMInvalidRequestError`.
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
import json
from typing import TYPE_CHECKING, Any

import httpx

from cora.agent.adapters.local_llm import LocalCompletion
from cora.infrastructure.ports.llm import (
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    LLMUsage,
)

if TYPE_CHECKING:
    from cora.infrastructure.ports.llm import LLMChatRequest

_DEFAULT_TIMEOUT_SECONDS = 600.0
_STRUCTURED_OUTPUT_NAME = "cora_decision"


class OpenAICompatibleBackend:
    """`LocalCompletionBackend` over an OpenAI-compatible chat endpoint.

    Construct with the server `base_url` (for example
    `http://localhost:11434` for Ollama or a vLLM host) and the served
    `model` name. An optional `api_key` becomes a bearer header for
    gateways that require one. An `httpx.AsyncClient` may be injected for
    tests or connection reuse; otherwise one is made per call and closed.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def aclose(self) -> None:
        """Close the injected client, if this backend owns one long-lived."""
        if self._client is not None:
            await self._client.aclose()

    async def complete(self, request: LLMChatRequest) -> LocalCompletion:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            try:
                response = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=self._to_chat_payload(request),
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError(str(exc)) from exc
            except httpx.HTTPError as exc:
                raise LLMServerError(f"network error: {exc}") from exc
            _raise_for_status(response)
            try:
                body = response.json()
            except ValueError as exc:
                raise LLMServerError(f"malformed response from local server: {exc}") from exc
            return self._to_local_completion(body)
        finally:
            if owns_client:
                await client.aclose()

    def _to_chat_payload(self, request: LLMChatRequest) -> dict[str, Any]:
        system_text = "\n".join(block.text for block in request.system.blocks)
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": request.user_message.text},
            ],
            "max_tokens": request.max_output_tokens,
            **_sampling_fields(request),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": _STRUCTURED_OUTPUT_NAME,
                    "schema": dict(request.structured_output_schema),
                },
            },
        }

    def _to_local_completion(self, body: dict[str, Any]) -> LocalCompletion:
        choices = body.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content")
        usage_raw = body.get("usage") or {}
        response_id = body.get("id")
        return LocalCompletion(
            parsed=_parse_json_object_or_none(content),
            raw_text=content if isinstance(content, str) else "",
            usage=LLMUsage(
                input_tokens=int(usage_raw.get("prompt_tokens") or 0),
                output_tokens=int(usage_raw.get("completion_tokens") or 0),
            ),
            model_id=str(body.get("model") or self._model),
            stop_reason=str(choice.get("finish_reason") or "stop"),
            response_id=str(response_id) if response_id is not None else None,
        )


def _sampling_fields(request: LLMChatRequest) -> dict[str, Any]:
    """Only send a dial the caller actually set (see `anthropic_llm`).

    vLLM does accept a `seed`, unlike the Anthropic API, so the build
    path is the one where replay could eventually be real. The port
    carries no seed yet, so this does not send one; recording a seed is
    the piece a future slice would add, and it would only ever make the
    facility-served path reproducible, never a vendor call.
    """
    fields: dict[str, Any] = {}
    if request.temperature is not None:
        fields["temperature"] = request.temperature
    if request.top_p is not None:
        fields["top_p"] = request.top_p
    return fields


def _raise_for_status(response: httpx.Response) -> None:
    code = response.status_code
    if code < 400:
        return
    if code == 429:
        raise LLMRateLimitError(f"429 from local server: {response.text}")
    if code >= 500:
        raise LLMServerError(f"{code} from local server: {response.text}")
    raise LLMInvalidRequestError(f"{code} from local server: {response.text}")


def _parse_json_object_or_none(content: object) -> dict[str, Any] | None:
    """Parse the message content into a JSON object, or None if it is not one."""
    if not isinstance(content, str):
        return None
    try:
        decoded = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


__all__ = ["OpenAICompatibleBackend"]
