"""Unit tests for Method.needed_supplies.

Covers:
  - State default + frozenset shape
  - Decider per-element validation (whitespace-only, oversized, trims)
  - Decider accepts empty + populated
  - Event payload sorted lexically (deterministic hash)
  - Event roundtrip preserves needed_supplies
  - Legacy event payload (no needed_supplies key) folds via additive
    evolution to empty frozenset (forward-compat critical pin)
  - Evolver fold for MethodDefined sets the field
  - Each transition (Versioned, Deprecated, ParametersSchemaUpdated)
    PRESERVES needed_supplies through (preserve-fields invariant)

Asymmetric-with-needed_family_ids design (str vs UUID) is exercised
implicitly throughout — needed_supplies elements are kind STRINGS,
never instance UUIDs.
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
    ExecutionPattern,
    InvalidMethodNeededSuppliesError,
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
    """Shared Capability fixture for these decider tests."""
    return Capability(
        id=UUID("01900000-0000-7000-8000-00000000c1da"),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


_CAP = _capability()

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


# ---------- Method state shape ----------


@pytest.mark.unit
def test_method_state_defaults_needed_supplies_to_empty_frozenset() -> None:
    """Legacy Methods (no payload key) and freshly-defined Methods
    that don't declare supplies both land at empty. The default-factory
    keeps state shape uniform."""
    method = Method(
        id=uuid4(),
        name=MethodName("X"),
    )
    assert method.needed_supplies == frozenset()


@pytest.mark.unit
def test_method_state_carries_supplied_needed_supplies() -> None:
    method = Method(
        id=uuid4(),
        name=MethodName("Tomography"),
        needed_supplies=frozenset({"PhotonBeam", "LiquidNitrogen"}),
    )
    assert method.needed_supplies == frozenset({"PhotonBeam", "LiquidNitrogen"})


# ---------- Decider validation ----------


@pytest.mark.unit
def test_decider_accepts_empty_needed_supplies() -> None:
    """Sample-cleaning Method valid: no Family AND no Supply
    requirement (purely procedural)."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAP.id,
            name="Sample Cleaning",
            needed_family_ids=frozenset(),
            needed_supplies=frozenset(),
        ),
        capability=_CAP,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].needed_supplies == ()


@pytest.mark.unit
def test_decider_accepts_populated_needed_supplies() -> None:
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAP.id,
            name="Tomography",
            needed_family_ids=frozenset(),
            needed_supplies=frozenset({"PhotonBeam", "LiquidNitrogen"}),
        ),
        capability=_CAP,
        now=_NOW,
        new_id=uuid4(),
    )
    assert set(events[0].needed_supplies) == {"PhotonBeam", "LiquidNitrogen"}


@pytest.mark.unit
def test_decider_trims_each_kind_string() -> None:
    """Each kind goes through validate_bounded_text (1-50 chars,
    trimmed). Mirrors Method's own MethodName trim behavior."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAP.id,
            name="X",
            needed_family_ids=frozenset(),
            needed_supplies=frozenset({"  PhotonBeam  ", "LiquidNitrogen"}),
        ),
        capability=_CAP,
        now=_NOW,
        new_id=uuid4(),
    )
    assert "PhotonBeam" in set(events[0].needed_supplies)
    assert "  PhotonBeam  " not in set(events[0].needed_supplies)


@pytest.mark.unit
def test_decider_rejects_whitespace_only_kind() -> None:
    with pytest.raises(InvalidMethodNeededSuppliesError):
        define_method.decide(
            state=None,
            command=DefineMethod(
                execution_pattern=ExecutionPattern.BATCH,
                capability_id=_CAP.id,
                name="X",
                needed_family_ids=frozenset(),
                needed_supplies=frozenset({"   "}),
            ),
            capability=_CAP,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decider_rejects_empty_kind() -> None:
    with pytest.raises(InvalidMethodNeededSuppliesError):
        define_method.decide(
            state=None,
            command=DefineMethod(
                execution_pattern=ExecutionPattern.BATCH,
                capability_id=_CAP.id,
                name="X",
                needed_family_ids=frozenset(),
                needed_supplies=frozenset({""}),
            ),
            capability=_CAP,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decider_rejects_oversized_kind() -> None:
    """Per-element bound is 50 chars (mirrors Supply.kind shape)."""
    with pytest.raises(InvalidMethodNeededSuppliesError):
        define_method.decide(
            state=None,
            command=DefineMethod(
                execution_pattern=ExecutionPattern.BATCH,
                capability_id=_CAP.id,
                name="X",
                needed_family_ids=frozenset(),
                needed_supplies=frozenset({"x" * 51}),
            ),
            capability=_CAP,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decider_accepts_max_length_kind() -> None:
    boundary = "x" * 50
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAP.id,
            name="X",
            needed_family_ids=frozenset(),
            needed_supplies=frozenset({boundary}),
        ),
        capability=_CAP,
        now=_NOW,
        new_id=uuid4(),
    )
    assert boundary in set(events[0].needed_supplies)


# ---------- Event payload determinism ----------


@pytest.mark.unit
def test_to_payload_sorts_needed_supplies_lexically() -> None:
    """Same logical kind set must serialize to the same payload bytes
    (idempotency-hash determinism). Sorting in to_payload is the
    contract."""
    event = MethodDefined(
        method_id=uuid4(),
        name="X",
        needed_family_ids=(),
        needed_supplies=("LiquidNitrogen", "PhotonBeam", "ComputePool"),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["needed_supplies"] == ["ComputePool", "LiquidNitrogen", "PhotonBeam"]


@pytest.mark.unit
def test_event_round_trips_with_needed_supplies() -> None:
    original = MethodDefined(
        method_id=uuid4(),
        name="Tomography",
        needed_family_ids=(),
        needed_supplies=("LiquidNitrogen", "PhotonBeam"),
        occurred_at=_NOW,
    )
    stored = _stored("MethodDefined", to_payload(original))
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    # Sets equal (payload sorts; from_stored preserves payload order).
    assert set(rebuilt.needed_supplies) == {"LiquidNitrogen", "PhotonBeam"}


# ---------- Legacy backward-compat (additive evolution) ----------


@pytest.mark.unit
def test_legacy_event_payload_folds_with_empty_needed_supplies() -> None:
    """Critical forward-compat pin. Legacy MethodDefined payloads
    have NO needed_supplies key. additive-evolution: from_stored uses
    payload.get(..., default), so the rebuilt event carries empty
    list, and the evolver folds into empty frozenset."""
    legacy_payload: dict[str, object] = {
        "method_id": str(uuid4()),
        "name": "Legacy Method",
        "needed_family_ids": [],
        "occurred_at": _NOW.isoformat(),
        # No needed_supplies key — legacy payload shape.
    }
    stored = _stored("MethodDefined", legacy_payload)
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    assert rebuilt.needed_supplies == ()
    state = evolve(None, rebuilt)
    assert state.needed_supplies == frozenset()


# ---------- Evolver fold ----------


@pytest.mark.unit
def test_evolve_method_defined_sets_needed_supplies() -> None:
    method_id = uuid4()
    event = MethodDefined(
        method_id=method_id,
        name="Tomography",
        needed_family_ids=(),
        needed_supplies=("PhotonBeam", "LiquidNitrogen"),
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.needed_supplies == frozenset({"PhotonBeam", "LiquidNitrogen"})


# ---------- Preserve-fields invariant per transition ----------


def _seed_state(supplies: frozenset[str]) -> Method:
    return evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="Tomography",
            needed_family_ids=(),
            needed_supplies=tuple(supplies),
            occurred_at=_NOW,
        ),
    )


@pytest.mark.unit
def test_evolve_method_versioned_preserves_needed_supplies() -> None:
    seed = _seed_state(frozenset({"PhotonBeam"}))
    after = evolve(seed, MethodVersioned(method_id=seed.id, version_tag="v2", occurred_at=_NOW))
    assert after.needed_supplies == frozenset({"PhotonBeam"})
    assert after.status is MethodStatus.VERSIONED


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_needed_supplies() -> None:
    seed = _seed_state(frozenset({"PhotonBeam", "LiquidNitrogen"}))
    after = evolve(seed, MethodDeprecated(method_id=seed.id, occurred_at=_NOW))
    assert after.needed_supplies == frozenset({"PhotonBeam", "LiquidNitrogen"})
    assert after.status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_preserves_needed_supplies() -> None:
    """Orthogonal-facet update must NOT wipe needed_supplies."""
    seed = _seed_state(frozenset({"PhotonBeam"}))
    after = evolve(
        seed,
        MethodParametersSchemaUpdated(
            method_id=seed.id,
            parameters_schema={"type": "object"},
            occurred_at=_NOW,
        ),
    )
    assert after.needed_supplies == frozenset({"PhotonBeam"})


@pytest.mark.unit
def test_fold_full_lifecycle_preserves_needed_supplies() -> None:
    """End-to-end: defined → versioned → schema-updated → deprecated.
    needed_supplies survives the whole chain."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(
                method_id=method_id,
                name="Tomography",
                needed_family_ids=(),
                needed_supplies=("PhotonBeam", "LiquidNitrogen"),
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
    assert state.needed_supplies == frozenset({"PhotonBeam", "LiquidNitrogen"})
    assert state.status is MethodStatus.DEPRECATED


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
    """The event class name does not change — additive payload
    evolution only. Pinned because subscribers route by event_type."""
    event = MethodDefined(
        method_id=uuid4(),
        name="X",
        needed_family_ids=(),
        needed_supplies=(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "MethodDefined"


# Suppress pyright warnings on the test-only state seed factory.
_ = UUID  # marker so the import is referenced (used by stored helper return type).
