"""Application-handler tests for the `end_iteration` slice.

Update-style handler via `make_procedure_update_handler`. Tests seed a
Procedure in `Running` with one iteration open via the shared
`_helpers.seed_running_procedure_with_open_iteration`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    ProcedureCannotEndIterationError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import end_iteration
from cora.operation.features.end_iteration import EndProcedureIteration
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import (
    seed_running_procedure,
    seed_running_procedure_with_open_iteration,
)

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 6, 13, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000e0e01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000e0e02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_open_iteration(store: InMemoryEventStore) -> None:
    await seed_running_procedure_with_open_iteration(
        store,
        procedure_id=_PROCEDURE_ID,
        iteration_index=1,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )


@pytest.mark.unit
async def test_handler_appends_iteration_ended_event() -> None:
    store = InMemoryEventStore()
    await _seed_open_iteration(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = end_iteration.bind(deps)

    await handler(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID, iteration_index=1, converged=False, reason="off by 2px"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 4
    assert events[3].event_type == "ProcedureIterationEnded"
    assert events[3].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "iteration_index": 1,
        "converged": False,
        "reason": "off by 2px",
        "occurred_at": _NOW.isoformat(),
        "advised_stop": None,
        "reasoning": None,
        "confidence": None,
        "confidence_source": None,
        "alternatives": [],
        "model_ref": None,
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = end_iteration.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            EndProcedureIteration(
                procedure_id=_PROCEDURE_ID, iteration_index=1, converged=True, reason=None
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_no_iteration_open() -> None:
    store = InMemoryEventStore()
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotEndIterationError):
        await end_iteration.bind(deps)(
            EndProcedureIteration(
                procedure_id=_PROCEDURE_ID, iteration_index=1, converged=True, reason=None
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny_and_does_not_append() -> None:
    store = InMemoryEventStore()
    await _seed_open_iteration(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = end_iteration.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            EndProcedureIteration(
                procedure_id=_PROCEDURE_ID, iteration_index=1, converged=True, reason=None
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3  # Registered + Started + IterationStarted only
