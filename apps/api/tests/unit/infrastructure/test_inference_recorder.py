"""Unit tests for the InferenceRecorder port surface and value types."""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.ports import (
    AgentInferenceTrace,
    NullInferenceRecorder,
)

_DECISION_ID = UUID("01900000-0000-7000-8000-0000000d0001")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000e0001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000a0001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000c0001")
_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)


def _trace() -> AgentInferenceTrace:
    return AgentInferenceTrace(
        decision_id=_DECISION_ID,
        event_id=_EVENT_ID,
        occurred_at=_NOW,
        operation_name="chat",
        provider_name="anthropic",
        request_model="claude-haiku-4-5",
    )


@pytest.mark.unit
def test_agent_inference_trace_is_frozen() -> None:
    trace = _trace()
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.request_model = "claude-opus-4-8"  # type: ignore[misc]


@pytest.mark.unit
def test_agent_inference_trace_optional_fields_default() -> None:
    trace = _trace()
    assert trace.response_model is None
    assert trace.finish_reasons == ()
    assert trace.input_tokens is None
    assert trace.output_tokens is None
    assert trace.request_max_tokens is None
    assert trace.agent_id is None
    assert trace.agent_name is None


@pytest.mark.unit
async def test_null_recorder_is_a_noop() -> None:
    """The Kernel default must accept a record call and do nothing,
    never raising, so unwired kernels stay inert."""
    recorder = NullInferenceRecorder()
    result = await recorder.record(
        _trace(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
    )
    assert result is None
