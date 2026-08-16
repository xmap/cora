"""Unit tests for the `get_run` query handler.

Mirrors `test_get_plan_handler.py`. Round-trip seed + get verifies
fold-on-read returns the started Run, composed into a `RunView`
(slice 13) mirroring `get_actor`'s `ActorView`. `capture_code` /
`observed_capture_path` resolution itself is covered by
`test_get_run_route.py` and the `get_run` contract tests; these tests
pin the handler's OWN contract (authz, fold-on-read, RunView shape).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    InMemoryCapturePathStore,
    Run,
    RunName,
    RunStatus,
)
from cora.run.aggregates.run.events import (
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features import get_run
from cora.run.features.get_run import GetRun
from tests.unit._helpers import RecordingAuthorize, build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000ff01")
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000ff02")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-00000000ff03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    plan_id: UUID,
    subject_id: UUID | None,
    name: str = "32-ID FlyScan",
) -> None:
    event = RunStarted(
        run_id=run_id,
        name=name,
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_run_for_known_id_with_subject() -> None:
    """Round-trip: seed sample run + get."""
    store = InMemoryEventStore()
    await _seed_run(store, _RUN_ID, plan_id=_PLAN_ID, subject_id=_SUBJECT_ID)
    deps = build_deps(ids=[_RUN_ID], now=_NOW, event_store=store)
    handler = get_run.bind(deps, capture_path_store=InMemoryCapturePathStore())
    view = await handler(
        GetRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.run == Run(
        id=_RUN_ID,
        name=RunName("32-ID FlyScan"),
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        status=RunStatus.RUNNING,
    )
    assert view.capture_code is None
    assert view.observed_capture_path is None


@pytest.mark.unit
async def test_handler_returns_run_for_known_id_without_subject() -> None:
    """Calibration / dark-field run: subject_id=None."""
    store = InMemoryEventStore()
    await _seed_run(store, _RUN_ID, plan_id=_PLAN_ID, subject_id=None, name="Dark field")
    deps = build_deps(ids=[_RUN_ID], now=_NOW, event_store=store)
    handler = get_run.bind(deps, capture_path_store=InMemoryCapturePathStore())
    view = await handler(
        GetRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.run.subject_id is None


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = build_deps(ids=[_RUN_ID], now=_NOW)
    handler = get_run.bind(deps, capture_path_store=InMemoryCapturePathStore())
    view = await handler(
        GetRun(run_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = RecordingAuthorize()
    deps = build_deps(ids=[_RUN_ID], now=_NOW, authz=tracking)

    handler = get_run.bind(deps, capture_path_store=InMemoryCapturePathStore())
    await handler(
        GetRun(run_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetRun", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_RUN_ID], now=_NOW, deny=True)
    handler = get_run.bind(deps, capture_path_store=InMemoryCapturePathStore())
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetRun(run_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_run_includes_get_run() -> None:
    deps = build_deps(ids=[_RUN_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.get_run)
