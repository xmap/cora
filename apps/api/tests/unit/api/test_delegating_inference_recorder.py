"""Unit tests for the composition-root DelegatingInferenceRecorder.

Drives the recorder against a spy `append_inferences` handler: asserts the
neutral `AgentInferenceTrace` maps onto the exact `AppendInferences` /
`ReasoningEntryInput` command, that principal / correlation / causation thread
through, and that the fire-and-forget contract holds (an authorization denial
or any other handler error is swallowed, never raised).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
import structlog

from cora.api._inference_recorder import DelegatingInferenceRecorder
from cora.decision.errors import UnauthorizedError
from cora.decision.features.append_inferences.command import AppendInferences
from cora.infrastructure.ports import AgentInferenceTrace
from cora.infrastructure.routing import NIL_SENTINEL_ID

_DECISION_ID = UUID("01900000-0000-7000-8000-0000000d0001")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000e0001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000a0001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000c0001")
_CAUSATION_ID = UUID("01900000-0000-7000-8000-0000000b0001")
_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)


class _SpyAppendInferences:
    """Spy conforming to the append_inferences `Handler` Protocol."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.commands: list[AppendInferences] = []
        self.principal_ids: list[UUID] = []
        self.correlation_ids: list[UUID] = []
        self.causation_ids: list[UUID | None] = []
        self._raises = raises

    async def __call__(
        self,
        command: AppendInferences,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.commands.append(command)
        self.principal_ids.append(principal_id)
        self.correlation_ids.append(correlation_id)
        self.causation_ids.append(causation_id)
        if self._raises is not None:
            raise self._raises
        return len(command.entries)


def _trace() -> AgentInferenceTrace:
    return AgentInferenceTrace(
        decision_id=_DECISION_ID,
        event_id=_EVENT_ID,
        occurred_at=_NOW,
        operation_name="chat",
        provider_name="anthropic",
        request_model="claude-haiku-4-5",
        response_model="claude-haiku-4-5-20260201",
        finish_reasons=("tool_use",),
        input_tokens=1280,
        output_tokens=214,
        request_max_tokens=1024,
        agent_id="01900000-0000-7000-8000-0000000a0099",
        agent_name="RunDebriefer",
    )


@pytest.mark.unit
async def test_record_maps_trace_to_append_inferences_command() -> None:
    spy = _SpyAppendInferences()
    recorder = DelegatingInferenceRecorder(spy)

    await recorder.record(
        _trace(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=_CAUSATION_ID,
    )

    assert len(spy.commands) == 1
    command = spy.commands[0]
    assert command.decision_id == _DECISION_ID
    assert len(command.entries) == 1
    entry = command.entries[0]
    assert entry.event_id == _EVENT_ID
    assert entry.occurred_at == _NOW
    assert entry.operation_name == "chat"
    assert entry.provider_name == "anthropic"
    assert entry.request_model == "claude-haiku-4-5"
    assert entry.response_model == "claude-haiku-4-5-20260201"
    assert entry.finish_reasons == ("tool_use",)
    assert entry.input_tokens == 1280
    assert entry.output_tokens == 214
    assert entry.request_max_tokens == 1024
    assert entry.agent_id == "01900000-0000-7000-8000-0000000a0099"
    assert entry.agent_name == "RunDebriefer"


@pytest.mark.unit
async def test_record_threads_envelope_identifiers() -> None:
    spy = _SpyAppendInferences()
    recorder = DelegatingInferenceRecorder(spy)

    await recorder.record(
        _trace(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=_CAUSATION_ID,
    )

    assert spy.principal_ids == [_PRINCIPAL_ID]
    assert spy.correlation_ids == [_CORRELATION_ID]
    assert spy.causation_ids == [_CAUSATION_ID]


@pytest.mark.unit
async def test_record_warns_distinctly_on_authorization_denial() -> None:
    """A denied AppendInferences (agent principal lacks the grant under a
    real Trust policy) must not propagate; it is logged LOUDLY and
    DISTINCTLY so a missing operator grant is visible, not a silent drop."""
    spy = _SpyAppendInferences(raises=UnauthorizedError("not permitted"))
    recorder = DelegatingInferenceRecorder(spy)

    with structlog.testing.capture_logs() as logs:
        result = await recorder.record(
            _trace(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            causation_id=_CAUSATION_ID,
        )
    assert result is None
    assert len(spy.commands) == 1
    events = [entry.get("event") for entry in logs]
    assert "inference_recorder.unauthorized" in events
    assert "inference_recorder.failed" not in events


@pytest.mark.unit
async def test_record_warns_on_unexpected_error() -> None:
    spy = _SpyAppendInferences(raises=RuntimeError("store down"))
    recorder = DelegatingInferenceRecorder(spy)

    with structlog.testing.capture_logs() as logs:
        result = await recorder.record(
            _trace(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            causation_id=_CAUSATION_ID,
        )
    assert result is None
    assert len(spy.commands) == 1
    events = [entry.get("event") for entry in logs]
    assert "inference_recorder.failed" in events
    assert "inference_recorder.unauthorized" not in events
