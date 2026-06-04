"""Unit tests for the `define_method` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.capability import (
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.recipe.aggregates.method import (
    InvalidMethodNameError,
    MethodCapabilityExecutorMismatchError,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ab01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c0d1")


async def _build_seeded_deps(
    *,
    ids: list[UUID] | None = None,
    deny: bool = False,
    capability_id: UUID = _CAPABILITY_ID,
    capability_shapes: frozenset[ExecutorShape] | None = None,
) -> tuple[InMemoryEventStore, Kernel]:
    """Build deps with a seeded Method-shaped Capability so the handler can
    load it without raising CapabilityNotFoundError. Returns (store, deps) for
    tests that want both."""
    store = InMemoryEventStore()
    await seed_capability(
        store, capability_id, shapes=capability_shapes or frozenset({ExecutorShape.METHOD})
    )
    deps = build_deps(ids=ids or [_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=deny)
    return store, deps


@pytest.mark.unit
async def test_handler_returns_generated_method_id() -> None:
    _, deps = await _build_seeded_deps()
    handler = define_method.bind(deps)

    result = await handler(
        DefineMethod(name="XRF Mapping", capability_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_method_defined_event_to_store() -> None:
    store, deps = await _build_seeded_deps()
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(
            name="XRF Fly Mapping",
            capability_id=_CAPABILITY_ID,
            needed_family_ids=frozenset({_CAP1, _CAP2}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    # Payload's needed_family_ids is sorted by string form
    # (deterministic). Compare exact bytes to lock the contract.
    assert stored.payload == {
        "method_id": str(_NEW_ID),
        "name": "XRF Fly Mapping",
        "needed_family_ids": sorted([str(_CAP1), str(_CAP2)]),
        # needed_supplies. Pinned by test_method_needed_supplies.py.
        "needed_supplies": [],
        # needed_assembly_ids. Pinned by test_method_needed_assembly_ids.py.
        "needed_assembly_ids": [],
        # and round-trips through MethodDefined as a UUID string.
        "capability_id": str(_CAPABILITY_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_handles_empty_needed_family_ids() -> None:
    """Procedural Method (no equipment requirement) lands as
    payload `needed_family_ids = []`."""
    store, deps = await _build_seeded_deps()
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(
            name="Sample Cleaning", capability_id=_CAPABILITY_ID, needed_family_ids=frozenset()
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["needed_family_ids"] == []


@pytest.mark.unit
async def test_handler_trims_method_name_via_value_object() -> None:
    store, deps = await _build_seeded_deps()
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="  XRF Mapping  ", capability_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["name"] == "XRF Mapping"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    _, deps = await _build_seeded_deps(deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefineMethod(name="X", capability_id=_CAPABILITY_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store, deps = await _build_seeded_deps(deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineMethod(name="X", capability_id=_CAPABILITY_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Method", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_method_name_error() -> None:
    _, deps = await _build_seeded_deps()
    handler = define_method.bind(deps)

    with pytest.raises(InvalidMethodNameError):
        await handler(
            DefineMethod(name="   ", capability_id=_CAPABILITY_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_emits_byte_identical_payload_for_same_capability_id() -> None:
    """Determinism pin: two DefineMethod calls with the same logical inputs,
    including the `capability_id` key, must produce byte-identical persisted
    `MethodDefined.payload` dicts. Required for idempotency-key hashing to stay
    stable across additive payload shape changes (see `with_idempotency`
    SHA256 over normalized request body)."""
    needed_family_ids = frozenset({_CAP1, _CAP2})

    # Run 1
    store_a, deps_a = await _build_seeded_deps()
    await define_method.bind(deps_a)(
        DefineMethod(
            name="XRF Fly Mapping",
            capability_id=_CAPABILITY_ID,
            needed_family_ids=needed_family_ids,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_a, _ = await store_a.load("Method", _NEW_ID)

    # Run 2 (fresh store + deps)
    store_b, deps_b = await _build_seeded_deps()
    await define_method.bind(deps_b)(
        DefineMethod(
            name="XRF Fly Mapping",
            capability_id=_CAPABILITY_ID,
            needed_family_ids=needed_family_ids,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_b, _ = await store_b.load("Method", _NEW_ID)

    assert events_a[0].payload == events_b[0].payload
    assert events_a[0].payload["capability_id"] == str(_CAPABILITY_ID)


@pytest.mark.unit
async def test_handler_loads_and_validates_bound_capability_when_set() -> None:
    """Happy path through the handler: handler loads the Capability stream via
    `load_capability`, passes the loaded state to the decider, and the
    persisted MethodDefined payload carries the bound capability_id."""
    store, deps = await _build_seeded_deps()
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="X", capability_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["capability_id"] == str(_CAPABILITY_ID)


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_stream_missing() -> None:
    """capability_id set on the command but no Capability stream exists for
    it. load_capability returns None; the decider raises
    CapabilityNotFoundError (mapped to 404 at the HTTP boundary)."""
    bogus = UUID("01900000-0000-7000-8000-deadbeefcafe")
    store = InMemoryEventStore()  # intentionally NO seed for `bogus`
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            DefineMethod(name="X", capability_id=bogus),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    method_events, version = await store.load("Method", _NEW_ID)
    assert method_events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_raises_executor_mismatch_when_capability_excludes_method() -> None:
    """capability_id binds to a Procedure-only Capability. Handler propagates
    MethodCapabilityExecutorMismatchError (mapped to 409). Critical: no Method
    event should be persisted when the cross-BC guard fires."""
    capability_id = UUID("01900000-0000-7000-8000-00000000c002")
    _, deps = await _build_seeded_deps(
        capability_id=capability_id, capability_shapes=frozenset({ExecutorShape.PROCEDURE})
    )
    handler = define_method.bind(deps)
    # Reuse the seeded store for the post-failure assertion.
    store: InMemoryEventStore = deps.event_store  # type: ignore[assignment]

    with pytest.raises(MethodCapabilityExecutorMismatchError) as exc_info:
        await handler(
            DefineMethod(name="X", capability_id=capability_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.capability_id == capability_id

    method_events, version = await store.load("Method", _NEW_ID)
    assert method_events == []
    assert version == 0


@pytest.mark.unit
def test_wire_recipe_returns_handlers_bundle_with_define_method() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.define_method)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store, deps = await _build_seeded_deps()
    handlers = wire_recipe(deps)

    await handlers.define_method(
        DefineMethod(name="X", capability_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation
