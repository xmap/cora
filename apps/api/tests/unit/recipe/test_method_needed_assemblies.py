"""Unit tests for Method.needed_assembly_ids.

Covers:
  - State default + frozenset shape
  - Decider accepts empty + populated
  - Event payload sorted lexically by UUID string form (deterministic hash)
  - Event roundtrip preserves needed_assembly_ids
  - Legacy event payload (no needed_assembly_ids key) folds via additive
    evolution to empty frozenset (forward-compat critical pin)
  - Evolver fold for MethodDefined sets the field
  - Each transition (Versioned, Deprecated, ParametersSchemaUpdated)
    PRESERVES needed_assembly_ids through (preserve-fields invariant)
  - content_subset includes needed_assembly_ids (content_hash anchor)

Symmetric with needed_family_ids: both reference Equipment-BC
aggregates by UUID. Where needed_family_ids points at the Family
type registry, needed_assembly_ids points at the Assembly composition
blueprint registry. Both are subject to eventual-consistency: ids
are NOT verified against the Equipment BC at decide time; mismatch
surfaces at Plan-binding when the picked Assets must include
Fixtures whose assembly_id covers the requirement.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    ExecutorShape,
)
from cora.recipe.aggregates.method import (
    Method,
    MethodDefined,
    MethodDeprecated,
    MethodName,
    MethodParametersSchemaUpdated,
    MethodStatus,
    MethodVersioned,
    event_type_name,
    evolve,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod


def _capability() -> Capability:
    return Capability(
        id=UUID("01900000-0000-7000-8000-00000000c1da"),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


_CAP = _capability()

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_ASM_A = UUID("01900000-0000-7000-8000-0000000a55a1")
_ASM_B = UUID("01900000-0000-7000-8000-0000000a55b2")
_ASM_C = UUID("01900000-0000-7000-8000-0000000a55c3")


# ---------- Method state shape ----------


@pytest.mark.unit
def test_method_state_defaults_needed_assembly_ids_to_empty_frozenset() -> None:
    """Legacy Methods (no payload key) and freshly-defined Methods
    that don't declare assemblies both land at empty. The default-factory
    keeps state shape uniform."""
    method = Method(id=uuid4(), name=MethodName("X"))
    assert method.needed_assembly_ids == frozenset()


@pytest.mark.unit
def test_method_state_carries_supplied_needed_assembly_ids() -> None:
    method = Method(
        id=uuid4(),
        name=MethodName("Tomography"),
        needed_assembly_ids=frozenset({_ASM_A, _ASM_B}),
    )
    assert method.needed_assembly_ids == frozenset({_ASM_A, _ASM_B})


# ---------- Decider plumbing ----------


@pytest.mark.unit
def test_decider_accepts_empty_needed_assembly_ids() -> None:
    """Procedural Method (no Assembly requirement) valid."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            capability_id=_CAP.id,
            name="Sample Cleaning",
            needed_family_ids=frozenset(),
            needed_assembly_ids=frozenset(),
        ),
        capability=_CAP,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].needed_assembly_ids == ()


@pytest.mark.unit
def test_decider_accepts_populated_needed_assembly_ids() -> None:
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            capability_id=_CAP.id,
            name="Tomography",
            needed_family_ids=frozenset(),
            needed_assembly_ids=frozenset({_ASM_A, _ASM_B}),
        ),
        capability=_CAP,
        now=_NOW,
        new_id=uuid4(),
    )
    assert set(events[0].needed_assembly_ids) == {_ASM_A, _ASM_B}


# ---------- Event payload determinism ----------


@pytest.mark.unit
def test_to_payload_sorts_needed_assembly_ids_lexically() -> None:
    """Same logical Assembly set must serialize to the same payload bytes
    (idempotency-hash determinism). Sorting by UUID string form is the
    contract (mirrors needed_family_ids)."""
    event = MethodDefined(
        method_id=uuid4(),
        name="X",
        needed_family_ids=(),
        needed_assembly_ids=(_ASM_C, _ASM_A, _ASM_B),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["needed_assembly_ids"] == sorted([str(_ASM_A), str(_ASM_B), str(_ASM_C)])


@pytest.mark.unit
def test_event_round_trips_with_needed_assembly_ids() -> None:
    original = MethodDefined(
        method_id=uuid4(),
        name="Tomography",
        needed_family_ids=(),
        needed_assembly_ids=(_ASM_A, _ASM_B),
        occurred_at=_NOW,
    )
    stored = _stored("MethodDefined", to_payload(original))
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    assert set(rebuilt.needed_assembly_ids) == {_ASM_A, _ASM_B}


# ---------- Legacy backward-compat (additive evolution) ----------


@pytest.mark.unit
def test_legacy_event_payload_folds_with_empty_needed_assembly_ids() -> None:
    """Critical forward-compat pin. Legacy MethodDefined payloads
    have NO needed_assembly_ids key. additive-evolution: from_stored uses
    payload.get(..., default), so the rebuilt event carries empty
    tuple, and the evolver folds into empty frozenset."""
    legacy_payload: dict[str, object] = {
        "method_id": str(uuid4()),
        "name": "Legacy Method",
        "needed_family_ids": [],
        "occurred_at": _NOW.isoformat(),
        # No needed_assembly_ids key, legacy payload shape.
    }
    stored = _stored("MethodDefined", legacy_payload)
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    assert rebuilt.needed_assembly_ids == ()
    state = evolve(None, rebuilt)
    assert state.needed_assembly_ids == frozenset()


# ---------- Evolver fold ----------


@pytest.mark.unit
def test_evolve_method_defined_sets_needed_assembly_ids() -> None:
    method_id = uuid4()
    event = MethodDefined(
        method_id=method_id,
        name="Tomography",
        needed_family_ids=(),
        needed_assembly_ids=(_ASM_A, _ASM_B),
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.needed_assembly_ids == frozenset({_ASM_A, _ASM_B})


# ---------- Preserve-fields invariant per transition ----------


def _seed_state(assemblies: frozenset[UUID]) -> Method:
    return evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="Tomography",
            needed_family_ids=(),
            needed_assembly_ids=tuple(assemblies),
            occurred_at=_NOW,
        ),
    )


@pytest.mark.unit
def test_evolve_method_versioned_preserves_needed_assembly_ids() -> None:
    seed = _seed_state(frozenset({_ASM_A}))
    after = evolve(seed, MethodVersioned(method_id=seed.id, version_tag="v2", occurred_at=_NOW))
    assert after.needed_assembly_ids == frozenset({_ASM_A})
    assert after.status is MethodStatus.VERSIONED


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_needed_assembly_ids() -> None:
    seed = _seed_state(frozenset({_ASM_A, _ASM_B}))
    after = evolve(seed, MethodDeprecated(method_id=seed.id, occurred_at=_NOW))
    assert after.needed_assembly_ids == frozenset({_ASM_A, _ASM_B})
    assert after.status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_preserves_needed_assembly_ids() -> None:
    """Orthogonal-facet update must NOT wipe needed_assembly_ids."""
    seed = _seed_state(frozenset({_ASM_A}))
    after = evolve(
        seed,
        MethodParametersSchemaUpdated(
            method_id=seed.id,
            parameters_schema={"type": "object"},
            occurred_at=_NOW,
        ),
    )
    assert after.needed_assembly_ids == frozenset({_ASM_A})


@pytest.mark.unit
def test_fold_full_lifecycle_preserves_needed_assembly_ids() -> None:
    """End-to-end: defined -> versioned -> schema-updated -> deprecated.
    needed_assembly_ids survives the whole chain."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(
                method_id=method_id,
                name="Tomography",
                needed_family_ids=(),
                needed_assembly_ids=(_ASM_A, _ASM_B),
                occurred_at=_NOW,
            ),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
            MethodParametersSchemaUpdated(
                method_id=method_id,
                parameters_schema={"type": "object"},
                occurred_at=_NOW,
            ),
            MethodDeprecated(method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.needed_assembly_ids == frozenset({_ASM_A, _ASM_B})
    assert state.status is MethodStatus.DEPRECATED


# ---------- content_subset / content_hash anchor ----------


@pytest.mark.unit
def test_content_subset_includes_needed_assembly_ids_sorted_by_string() -> None:
    """needed_assembly_ids participates in content identity (anti-hook #10);
    changing the set MUST produce a different content_hash. The subset
    materializes as a sorted list of UUID strings so the canonical bytes
    are deterministic across worker processes."""
    method = Method(
        id=uuid4(),
        name=MethodName("Tomography"),
        needed_assembly_ids=frozenset({_ASM_C, _ASM_A, _ASM_B}),
    )
    subset = method.content_subset()
    assert subset["needed_assembly_ids"] == sorted([str(_ASM_A), str(_ASM_B), str(_ASM_C)])


@pytest.mark.unit
def test_content_subset_differs_when_needed_assembly_ids_differs() -> None:
    """Same name + same family-ids + same supplies, but different
    Assembly set, content_subset must diverge so content_hash will."""
    base_kwargs: dict[str, object] = {
        "id": uuid4(),
        "name": MethodName("Tomography"),
    }
    method_a = Method(**base_kwargs, needed_assembly_ids=frozenset({_ASM_A}))  # type: ignore[arg-type]
    method_b = Method(**base_kwargs, needed_assembly_ids=frozenset({_ASM_B}))  # type: ignore[arg-type]
    assert method_a.content_subset() != method_b.content_subset()


# ---------- Helper ----------


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Method",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- event_type_name (sanity) ----------


@pytest.mark.unit
def test_event_type_name_for_method_defined_unchanged() -> None:
    """The event class name does not change; additive payload
    evolution only. Pinned because subscribers route by event_type."""
    event = MethodDefined(
        method_id=uuid4(),
        name="X",
        needed_family_ids=(),
        needed_assembly_ids=(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "MethodDefined"
