"""Application-handler tests for `register_procedure` slice.

In-memory event store + AllowAllAuthorize (or DenyAllAuthorize). The
idempotency-wrap is applied at wire.py and is not exercised here;
we test the bare handler returned by `register_procedure.bind(deps)`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.operation.aggregates.procedure import (
    ProcedureCapabilityExecutorMismatchError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import register_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.recipe.aggregates.capability import (
    CapabilityNotFoundError,
    ExecutorShape,
)
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit._helpers import seed_capability as _seed_capability_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000c0a01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0a02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_ASSET_ID = UUID("01900000-0000-7000-8000-0000000c0a11")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_capability(
    store: InMemoryEventStore,
    capability_id: UUID,
    *,
    shapes: frozenset[ExecutorShape] | None = None,
) -> None:
    """Thin per-file wrapper around the shared `seed_capability` that
    pins this file's `_NOW`. Defaults to `{Procedure}` (this slice
    validates executor-shape membership for Procedure)."""
    await _seed_capability_shared(
        store,
        capability_id,
        shapes=shapes or frozenset({ExecutorShape.PROCEDURE}),
        now=_NOW,
    )


@pytest.mark.unit
async def test_handler_returns_generated_procedure_id() -> None:
    deps = _build_deps()
    handler = register_procedure.bind(deps)
    result = await handler(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_procedure_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({_ASSET_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Procedure", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ProcedureRegistered"
    assert stored.payload == {
        "procedure_id": str(_NEW_ID),
        "name": "2-BM rotation-axis alignment",
        "kind": "alignment",
        "target_asset_ids": [str(_ASSET_ID)],
        "parent_run_id": None,
        "capability_id": None,
        "recipe_id": None,
        "max_consecutive_unconverged_iterations": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterProcedure"}


@pytest.mark.unit
async def test_handler_appends_phase_of_run_with_parent_run_id() -> None:
    parent_run = UUID("01900000-0000-7000-8000-0000000c0a99")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(
            name="Mid-run alignment",
            kind="alignment",
            parent_run_id=parent_run,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].payload["parent_run_id"] == str(parent_run)


@pytest.mark.unit
async def test_handler_trims_kind_and_name() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(name="  Vessel-A bakeout  ", kind="  bakeout  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].payload["name"] == "Vessel-A bakeout"
    assert events[0].payload["kind"] == "bakeout"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_procedure.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterProcedure(name="X", kind="bakeout"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterProcedure(name="X", kind="bakeout"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Procedure", _NEW_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(name="X", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_operation_includes_register_procedure() -> None:
    from cora.operation import OperationHandlers, wire_operation

    deps = _build_deps()
    handlers = wire_operation(deps)
    assert isinstance(handlers, OperationHandlers)
    assert callable(handlers.register_procedure)
    assert callable(handlers.get_procedure)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    from cora.operation import wire_operation

    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_operation(deps)

    await handlers.register_procedure(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].causation_id == causation


# ---------- cross-BC capability tests ----------


@pytest.mark.unit
async def test_handler_emits_byte_identical_payload_for_same_capability_id() -> None:
    """Determinism pin: two RegisterProcedure calls with the same logical
    inputs, including a non-None `capability_id`, must produce byte-identical
    persisted `ProcedureRegistered.payload` dicts. Mirrors the sibling pin at
    test_define_method_handler.py; keeps idempotency-key SHA256 hashing stable
    across additive payload shape changes."""
    capability_id = UUID("01900000-0000-7000-8000-0000000c00de")

    # Run 1
    store_a = InMemoryEventStore()
    await _seed_capability(store_a, capability_id)
    deps_a = _build_deps(event_store=store_a)
    await register_procedure.bind(deps_a)(
        RegisterProcedure(
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({_ASSET_ID}),
            capability_id=capability_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_a, _ = await store_a.load("Procedure", _NEW_ID)

    # Run 2 (fresh store + deps)
    store_b = InMemoryEventStore()
    await _seed_capability(store_b, capability_id)
    deps_b = _build_deps(event_store=store_b)
    await register_procedure.bind(deps_b)(
        RegisterProcedure(
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({_ASSET_ID}),
            capability_id=capability_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_b, _ = await store_b.load("Procedure", _NEW_ID)

    assert events_a[0].payload == events_b[0].payload
    assert events_a[0].payload["capability_id"] == str(capability_id)


@pytest.mark.unit
async def test_handler_loads_and_validates_bound_capability_when_set() -> None:
    """Happy path: when RegisterProcedure.capability_id is set, the handler
    loads the Capability stream via `load_capability`, passes the loaded state
    to the decider, and the persisted ProcedureRegistered payload carries the
    bound capability_id."""
    capability_id = UUID("01900000-0000-7000-8000-0000000c00d1")
    store = InMemoryEventStore()
    await _seed_capability(store, capability_id)
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)

    await handler(
        RegisterProcedure(name="X", kind="alignment", capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].payload["capability_id"] == str(capability_id)


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_stream_missing() -> None:
    """capability_id set on the command but no Capability stream exists for it.
    Decider raises `CapabilityNotFoundError` (mapped to 404 via operation
    routes)."""
    bogus = UUID("01900000-0000-7000-8000-deadbeefcafe")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            RegisterProcedure(name="X", kind="alignment", capability_id=bogus),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    procedure_events, version = await store.load("Procedure", _NEW_ID)
    assert procedure_events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_raises_executor_mismatch_when_capability_excludes_procedure() -> None:
    """capability_id binds to a Method-only Capability. Handler propagates
    ProcedureCapabilityExecutorMismatchError (mapped to 409). Critical: no
    Procedure event should be persisted when the cross-BC guard fires."""
    capability_id = UUID("01900000-0000-7000-8000-0000000c00d2")
    store = InMemoryEventStore()
    await _seed_capability(store, capability_id, shapes=frozenset({ExecutorShape.METHOD}))
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)

    with pytest.raises(ProcedureCapabilityExecutorMismatchError) as exc_info:
        await handler(
            RegisterProcedure(name="X", kind="alignment", capability_id=capability_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.capability_id == capability_id

    procedure_events, version = await store.load("Procedure", _NEW_ID)
    assert procedure_events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_skips_capability_load_when_command_omits_capability_id() -> None:
    """When capability_id is None on the command, the handler does NOT call
    load_capability, so Procedures with no template binding (including
    ceremony Procedures) stay cost-free. Pinned via a sentinel event store
    that raises if Capability is loaded."""

    class _CapabilityLoadGuard(InMemoryEventStore):
        async def load(self, stream_type: str, stream_id: UUID):  # type: ignore[override]
            assert stream_type != "Capability", (
                "load_capability should not run when RegisterProcedure.capability_id is None"
            )
            return await super().load(stream_type, stream_id)

    store = _CapabilityLoadGuard()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)

    await handler(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].payload["capability_id"] is None
