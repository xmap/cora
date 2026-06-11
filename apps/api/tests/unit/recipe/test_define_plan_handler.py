"""Unit tests for the `define_plan` application handler.

This handler is the first in the codebase to pre-load upstream
aggregate state (Practice, Method, bound Assets) before reaching
the pure decider — gate-review Q5's canonical pattern. These tests
exercise the pre-load paths (existence checks, error propagation)
and the integration with the decider.

Test setup uses a `_seed_*` family of helpers that directly append
events to the in-memory store, bypassing the upstream BCs' handlers.
This keeps the test boilerplate tractable (single deps with one
FixedIdGenerator dedicated to the Plan under test) and the test
focus on Plan handler behavior, not upstream aggregate behavior.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.aggregates.asset.events import (
    AssetDecommissioned,
    AssetFamilyAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import (
    to_payload as asset_to_payload,
)
from cora.equipment.aggregates.family import Affordance, FamilyNotFoundError
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
)
from cora.equipment.aggregates.family.events import (
    event_type_name as family_event_type_name,
)
from cora.equipment.aggregates.family.events import (
    to_payload as family_to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityDefined,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (
    to_payload as capability_to_payload,
)
from cora.recipe.aggregates.method import MethodNotFoundError
from cora.recipe.aggregates.method.events import (
    MethodDefined,
)
from cora.recipe.aggregates.method.events import (
    MethodDeprecated as MethodDeprecatedEvent,
)
from cora.recipe.aggregates.method.events import (
    event_type_name as method_event_type_name,
)
from cora.recipe.aggregates.method.events import (
    to_payload as method_to_payload,
)
from cora.recipe.aggregates.plan import (
    InvalidPlanNameError,
    PlanAffordancesNotSatisfiedError,
    PlanAssetDecommissionedError,
    PlanAssetsRequiredError,
    PlanBoundMethodDeprecatedError,
    PlanBoundPracticeDeprecatedError,
    PlanFamiliesNotSatisfiedError,
)
from cora.recipe.aggregates.practice import PracticeNotFoundError
from cora.recipe.aggregates.practice.events import (
    PracticeDefined,
)
from cora.recipe.aggregates.practice.events import (
    PracticeDeprecated as PracticeDeprecatedEvent,
)
from cora.recipe.aggregates.practice.events import (
    event_type_name as practice_event_type_name,
)
from cora.recipe.aggregates.practice.events import (
    to_payload as practice_to_payload,
)
from cora.recipe.features import define_plan
from cora.recipe.features.define_plan import DefinePlan
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ee01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


# ---------- Direct event-seeding helpers ----------


async def _append(
    store: InMemoryEventStore,
    *,
    stream_type: str,
    stream_id: UUID,
    expected_version: int,
    event_type: str,
    payload: dict[str, object],
    command_name: str,
) -> None:
    new_event = to_new_event(
        event_type=event_type,
        payload=payload,
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type=stream_type,
        stream_id=stream_id,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_method(
    store: InMemoryEventStore,
    method_id: UUID,
    *,
    needed_family_ids: frozenset[UUID] = frozenset(),
    capability_id: UUID | None = None,
    deprecated: bool = False,
) -> None:
    event = MethodDefined(
        method_id=method_id,
        name="Test Method",
        needed_family_ids=tuple(sorted(needed_family_ids, key=str)),
        capability_id=capability_id,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Method",
        stream_id=method_id,
        expected_version=0,
        event_type=method_event_type_name(event),
        payload=method_to_payload(event),
        command_name="DefineMethod",
    )
    if deprecated:
        deprecated_event = MethodDeprecatedEvent(method_id=method_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Method",
            stream_id=method_id,
            expected_version=1,
            event_type=method_event_type_name(deprecated_event),
            payload=method_to_payload(deprecated_event),
            command_name="DeprecateMethod",
        )


async def _seed_practice(
    store: InMemoryEventStore,
    practice_id: UUID,
    *,
    method_id: UUID,
    site_id: UUID | None = None,
    deprecated: bool = False,
) -> None:
    event = PracticeDefined(
        practice_id=practice_id,
        name="Test Practice",
        method_id=method_id,
        site_id=site_id or uuid4(),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Practice",
        stream_id=practice_id,
        expected_version=0,
        event_type=practice_event_type_name(event),
        payload=practice_to_payload(event),
        command_name="DefinePractice",
    )
    if deprecated:
        deprecated_event = PracticeDeprecatedEvent(practice_id=practice_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Practice",
            stream_id=practice_id,
            expected_version=1,
            event_type=practice_event_type_name(deprecated_event),
            payload=practice_to_payload(deprecated_event),
            command_name="DeprecatePractice",
        )


async def _seed_capability(
    store: InMemoryEventStore,
    capability_id: UUID,
    *,
    required_affordances: frozenset[Affordance] = frozenset(),
    shapes: frozenset[ExecutorShape] = frozenset({ExecutorShape.METHOD}),
) -> None:
    """Seed a Recipe Capability stream for cross-BC tests."""
    event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.x").value,
        name=CapabilityName("X").value,
        required_affordances=required_affordances,
        executor_shapes=shapes,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        event_type=capability_event_type_name(event),
        payload=capability_to_payload(event),
        command_name="DefineCapability",
    )


async def _seed_family(
    store: InMemoryEventStore,
    family_id: UUID,
    *,
    affordances: frozenset[Affordance] = frozenset(),
) -> None:
    """Seed an Equipment Family stream for cross-BC tests."""
    event = FamilyDefined(
        family_id=family_id,
        name="TestFamily",
        affordances=affordances,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Family",
        stream_id=family_id,
        expected_version=0,
        event_type=family_event_type_name(event),
        payload=family_to_payload(event),
        command_name="DefineFamily",
    )


async def _seed_asset(
    store: InMemoryEventStore,
    asset_id: UUID,
    *,
    capabilities: frozenset[UUID] = frozenset(),
    decommissioned: bool = False,
) -> None:
    register_event = AssetRegistered(
        asset_id=asset_id,
        name="TestAsset",
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    await _append(
        store,
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        event_type=asset_event_type_name(register_event),
        payload=asset_to_payload(register_event),
        command_name="RegisterAsset",
    )
    version = 1
    for cap_id in sorted(capabilities, key=str):
        cap_event = AssetFamilyAdded(asset_id=asset_id, family_id=cap_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(cap_event),
            payload=asset_to_payload(cap_event),
            command_name="AddAssetFamily",
        )
        version += 1
    if decommissioned:
        dc_event = AssetDecommissioned(
            asset_id=asset_id, occurred_at=_NOW, decommissioned_by=ActorId(uuid4())
        )
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(dc_event),
            payload=asset_to_payload(dc_event),
            command_name="DecommissionAsset",
        )


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_returns_generated_plan_id() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    cap = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id, needed_family_ids=frozenset({cap}))
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({cap}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    result = await handler(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_plan_defined_event_to_store() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    cap = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id, needed_family_ids=frozenset({cap}))
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({cap}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    await handler(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "PlanDefined"
    assert stored.schema_version == 1
    assert stored.payload["plan_id"] == str(_NEW_ID)
    assert stored.payload["practice_id"] == str(practice_id)
    assert stored.payload["asset_ids"] == [str(asset_id)]
    assert stored.payload["method_id"] == str(method_id)
    assert stored.payload["method_needed_family_ids_snapshot"] == [str(cap)]
    assert stored.payload["asset_families_snapshot"] == {str(asset_id): [str(cap)]}
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefinePlan"}


@pytest.mark.unit
async def test_handler_trims_plan_name_via_value_object() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    await handler(
        DefinePlan(name="  X  ", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Plan", _NEW_ID)
    assert events[0].payload["name"] == "X"


# ---------- Authorization ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = define_plan.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefinePlan(name="X", practice_id=uuid4(), asset_ids=frozenset({uuid4()})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_pre_load_when_denied() -> None:
    """Authorization runs BEFORE the cross-aggregate pre-loads. When
    denied, no Practice/Method/Asset loads happen — important for
    avoiding unnecessary I/O on denied requests."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = define_plan.bind(deps)

    # Don't seed any prerequisites; if the handler tried to load
    # before checking authorize, it would raise PracticeNotFoundError.
    with pytest.raises(UnauthorizedError):
        await handler(
            DefinePlan(name="X", practice_id=uuid4(), asset_ids=frozenset({uuid4()})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Plan", _NEW_ID)
    assert events == []
    assert version == 0


# ---------- Pre-load: NotFoundError paths ----------


@pytest.mark.unit
async def test_handler_raises_practice_not_found_when_practice_missing() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_plan.bind(deps)

    missing_practice_id = uuid4()
    with pytest.raises(PracticeNotFoundError) as exc_info:
        await handler(
            DefinePlan(
                name="X",
                practice_id=missing_practice_id,
                asset_ids=frozenset({uuid4()}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.practice_id == missing_practice_id


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_referenced_method_missing() -> None:
    """Practice exists but its method_id doesn't resolve (dangling
    eventual-consistency ref)."""
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    # Practice references a method_id that doesn't exist in the store.
    await _seed_practice(store, practice_id, method_id=uuid4())
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_any_bound_asset_missing() -> None:
    """One of the bound asset_ids doesn't exist in the Asset stream."""
    method_id = uuid4()
    practice_id = uuid4()
    existing_asset_id = uuid4()
    missing_asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, existing_asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            DefinePlan(
                name="X",
                practice_id=practice_id,
                asset_ids=frozenset({existing_asset_id, missing_asset_id}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Decider error propagation ----------


@pytest.mark.unit
async def test_handler_propagates_practice_deprecated_error() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id, deprecated=True)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(PlanBoundPracticeDeprecatedError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_method_deprecated_error() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id, deprecated=True)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(PlanBoundMethodDeprecatedError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_asset_decommissioned_error() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, decommissioned=True)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(PlanAssetDecommissionedError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_capabilities_not_satisfied_error() -> None:
    needed_cap = uuid4()
    different_cap = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id, needed_family_ids=frozenset({needed_cap}))
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({different_cap}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(PlanFamiliesNotSatisfiedError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_invalid_plan_name_error() -> None:
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(InvalidPlanNameError):
        await handler(
            DefinePlan(name="   ", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_invalid_plan_error_for_empty_asset_ids() -> None:
    """Note: Pydantic min_length=1 catches this at the API boundary.
    The handler-level check is defensive for direct in-process callers
    (sagas, tests, MCP — though MCP also enforces min_length=1)."""
    practice_id = uuid4()
    method_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(PlanAssetsRequiredError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Causation propagation ----------


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    await handler(
        DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Plan", _NEW_ID)
    assert events[0].causation_id == causation


# ---------- Wire smoke ----------


@pytest.mark.unit
def test_wire_recipe_returns_handlers_bundle_with_plan() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.define_plan)
    assert callable(handlers.get_plan)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_recipe(deps)

    await handlers.define_plan(
        DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Plan", _NEW_ID)
    assert events[0].causation_id == causation


# ---------- Affordance-cover cross-BC tests ----------


@pytest.mark.unit
async def test_handler_skips_capability_and_family_loads_when_method_has_no_capability() -> None:
    """Compat path: Methods with no capability_id do NOT trigger Capability +
    Family loads. Pinned via a sentinel event store that raises if either
    stream type is loaded; the Plan creation still succeeds end-to-end."""

    class _CapabilityFamilyLoadGuard(InMemoryEventStore):
        async def load(self, stream_type: str, stream_id: UUID):  # type: ignore[override]
            assert stream_type not in ("Capability", "Family"), (
                f"Should not load {stream_type} when Method.capability_id is None"
            )
            return await super().load(stream_type, stream_id)

    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = _CapabilityFamilyLoadGuard()
    await _seed_method(store, method_id)  # no capability_id, compat shape
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    plan_id = await handler(
        DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert plan_id == _NEW_ID


@pytest.mark.unit
async def test_handler_loads_capability_and_families_when_method_has_capability_id() -> None:
    """Happy path: when Method.capability_id is set, the handler loads the
    Capability + every Family referenced by bound Assets, the decider verifies
    affordance coverage, and the Plan persists. Affordance union here (single
    Family carrying ROTATABLE) covers the single required affordance
    (ROTATABLE)."""
    family_id = uuid4()
    capability_id = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_capability(
        store, capability_id, required_affordances=frozenset({Affordance.ROTATABLE})
    )
    await _seed_family(store, family_id, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_method(
        store,
        method_id,
        needed_family_ids=frozenset({family_id}),
        capability_id=capability_id,
    )
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({family_id}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    plan_id = await handler(
        DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert plan_id == _NEW_ID


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_method_points_at_missing_stream() -> None:
    """Sad path: Method.capability_id references a Capability stream that
    does not exist. Handler raises `CapabilityNotFoundError` (mapped to 404).
    Pinned because the cross-BC reference is eventual-consistency at the
    Method side, so the integrity check has to land here."""
    family_id = uuid4()
    bogus_capability = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    # Note: NO _seed_capability for bogus_capability — that's the bug.
    await _seed_family(store, family_id, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_method(
        store,
        method_id,
        needed_family_ids=frozenset({family_id}),
        capability_id=bogus_capability,
    )
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({family_id}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_family_not_found_when_asset_references_missing_family() -> None:
    """Sad path: an Asset's `family_ids` references a Family UUID whose stream
    doesn't exist. With the affordance-cover fan-out enabled (Method has
    capability_id), the handler can't compute the affordance union without
    the Family. Raises `FamilyNotFoundError`; surfaces as 404."""
    bogus_family = uuid4()
    capability_id = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_capability(
        store, capability_id, required_affordances=frozenset({Affordance.ROTATABLE})
    )
    # Note: NO _seed_family for bogus_family — that's the bug.
    await _seed_method(
        store,
        method_id,
        needed_family_ids=frozenset({bogus_family}),
        capability_id=capability_id,
    )
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({bogus_family}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_affordances_not_satisfied_error() -> None:
    """Full-stack: every needed Family is bound (family-id check passes), but
    the union of Family.affordances misses one of
    Capability.required_affordances. Handler propagates
    `PlanAffordancesNotSatisfiedError` (mapped to 409)."""
    family_id = uuid4()
    capability_id = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    store = InMemoryEventStore()
    await _seed_capability(
        store,
        capability_id,
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}),
    )
    # Family carries only ROTATABLE; TRIGGERABLE is missing from the union.
    await _seed_family(store, family_id, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_method(
        store,
        method_id,
        needed_family_ids=frozenset({family_id}),
        capability_id=capability_id,
    )
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_asset(store, asset_id, capabilities=frozenset({family_id}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_plan.bind(deps)

    with pytest.raises(PlanAffordancesNotSatisfiedError) as exc_info:
        await handler(
            DefinePlan(name="X", practice_id=practice_id, asset_ids=frozenset({asset_id})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.missing_affordances == frozenset({Affordance.TRIGGERABLE.value})
