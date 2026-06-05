"""Unit tests for `controlport.dispatch` structlog event + correlation_id contextvar.

Locks the dispatch instrumentation surface added in the PseudoAxis
slice: `InMemoryControlPort.write` emits a `controlport.dispatch`
event on entry, threads the `correlation_id` from the
`with_dispatch_correlation_id` ContextVar scope, emits a second
`controlport.dispatch.failed` event when the write raises
`ControlNotConnectedError`, and the contextvar resets cleanly to its
prior value on context-manager exit (including via exception).
"""

from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.operation._control_dispatch_context import (
    get_dispatch_correlation_id,
    with_dispatch_correlation_id,
)
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.ports.control_port import ControlNotConnectedError

_ADDRESS = "2bm:rot:val"
_DISPATCH_EVENT = "controlport.dispatch"
_DISPATCH_COMPLETED_EVENT = "controlport.dispatch.completed"
_DISPATCH_FAILED_EVENT = "controlport.dispatch.failed"


def _dispatch_entries(
    captured: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    return [e for e in captured if e.get("event") == _DISPATCH_EVENT]


def _completed_entries(
    captured: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    return [e for e in captured if e.get("event") == _DISPATCH_COMPLETED_EVENT]


def _failed_entries(
    captured: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    return [e for e in captured if e.get("event") == _DISPATCH_FAILED_EVENT]


@pytest.mark.unit
async def test_write_inside_correlation_scope_emits_dispatch_event_with_correlation_id() -> None:
    port = InMemoryControlPort()
    port.simulate_connect(_ADDRESS)
    correlation_id = uuid4()

    with (
        structlog.testing.capture_logs() as captured,
        with_dispatch_correlation_id(correlation_id),
    ):
        await port.write(_ADDRESS, 3.14)

    dispatch = _dispatch_entries(captured)
    assert len(dispatch) == 1
    entry = dispatch[0]
    assert entry["correlation_id"] == str(correlation_id)
    assert entry["address"] == _ADDRESS
    assert entry["operation"] == "write"
    assert entry["status"] == "started"


@pytest.mark.unit
async def test_write_outside_correlation_scope_emits_dispatch_event_with_none_correlation_id() -> (
    None
):
    port = InMemoryControlPort()
    port.simulate_connect(_ADDRESS)

    with structlog.testing.capture_logs() as captured:
        await port.write(_ADDRESS, 1.0)

    dispatch = _dispatch_entries(captured)
    assert len(dispatch) == 1
    assert dispatch[0]["correlation_id"] is None


@pytest.mark.unit
async def test_write_success_inside_scope_emits_completed_event_with_correlation_id() -> None:
    port = InMemoryControlPort()
    port.simulate_connect(_ADDRESS)
    correlation_id = uuid4()

    with (
        structlog.testing.capture_logs() as captured,
        with_dispatch_correlation_id(correlation_id),
    ):
        await port.write(_ADDRESS, 2.0)

    completed = _completed_entries(captured)
    assert len(completed) == 1
    entry = completed[0]
    assert entry["correlation_id"] == str(correlation_id)
    assert entry["address"] == _ADDRESS
    assert entry["status"] == "completed"
    assert _failed_entries(captured) == []


@pytest.mark.unit
async def test_write_on_disconnected_address_emits_failed_event_with_exception_class() -> None:
    port = InMemoryControlPort()
    correlation_id = uuid4()

    with (
        structlog.testing.capture_logs() as captured,
        with_dispatch_correlation_id(correlation_id),
        pytest.raises(ControlNotConnectedError),
    ):
        await port.write(_ADDRESS, 5.0)

    dispatch = _dispatch_entries(captured)
    failed = _failed_entries(captured)
    assert len(dispatch) == 1
    assert len(failed) == 1
    assert _completed_entries(captured) == []
    failure = failed[0]
    assert failure["correlation_id"] == str(correlation_id)
    assert failure["address"] == _ADDRESS
    assert failure["status"] == "failed"
    assert failure["error_class"] == ControlNotConnectedError.__name__
    assert failure["operation"] == "write"


@pytest.mark.unit
async def test_write_failure_outside_scope_emits_failed_event_with_none_correlation_id() -> None:
    port = InMemoryControlPort()

    with structlog.testing.capture_logs() as captured, pytest.raises(ControlNotConnectedError):
        await port.write(_ADDRESS, 0)

    failed = _failed_entries(captured)
    assert len(failed) == 1
    assert failed[0]["correlation_id"] is None
    assert failed[0]["error_class"] == ControlNotConnectedError.__name__


@pytest.mark.unit
def test_contextvar_returns_none_outside_any_scope() -> None:
    assert get_dispatch_correlation_id() is None


@pytest.mark.unit
def test_contextvar_resets_after_context_manager_exits() -> None:
    correlation_id = uuid4()
    assert get_dispatch_correlation_id() is None
    with with_dispatch_correlation_id(correlation_id):
        assert get_dispatch_correlation_id() == correlation_id
    assert get_dispatch_correlation_id() is None


@pytest.mark.unit
def test_contextvar_resets_after_context_manager_exits_via_exception() -> None:
    correlation_id = uuid4()
    sentinel = RuntimeError("propagate")
    with pytest.raises(RuntimeError) as exc_info, with_dispatch_correlation_id(correlation_id):
        assert get_dispatch_correlation_id() == correlation_id
        raise sentinel
    assert exc_info.value is sentinel
    assert get_dispatch_correlation_id() is None


@pytest.mark.unit
def test_contextvar_nested_scopes_restore_outer_value_on_inner_exit() -> None:
    outer = uuid4()
    inner = uuid4()
    assert outer != inner
    with with_dispatch_correlation_id(outer):
        assert get_dispatch_correlation_id() == outer
        with with_dispatch_correlation_id(inner):
            assert get_dispatch_correlation_id() == inner
        assert get_dispatch_correlation_id() == outer
    assert get_dispatch_correlation_id() is None


@pytest.mark.unit
async def test_write_correlation_id_serialized_as_str_of_uuid() -> None:
    port = InMemoryControlPort()
    port.simulate_connect(_ADDRESS)
    correlation_id = UUID("12345678-1234-5678-1234-567812345678")

    with (
        structlog.testing.capture_logs() as captured,
        with_dispatch_correlation_id(correlation_id),
    ):
        await port.write(_ADDRESS, 7)

    dispatch = _dispatch_entries(captured)
    assert len(dispatch) == 1
    assert dispatch[0]["correlation_id"] == "12345678-1234-5678-1234-567812345678"
