"""Unit tests for the Role aggregate evolver + serialization round-trip."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import (
    RoleDefined,
    RoleId,
    RoleName,
    SignalType,
    event_type_name,
    evolve,
    fold,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ROLE_ID = UUID("01900000-0000-7000-8000-000000007ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000007be1")
_CORR = UUID("01900000-0000-7000-8000-0000000000aa")
_PRINC = UUID("01900000-0000-7000-8000-000000000099")


def _defined() -> RoleDefined:
    return RoleDefined(
        role_id=_ROLE_ID,
        name="Imager",
        docstring="Acquires 2D image frames on exposure or trigger.",
        occurred_at=_NOW,
        required_affordances=frozenset({Affordance.IMAGEABLE}),
        optional_affordances=frozenset({Affordance.BINNABLE}),
        produces=frozenset({SignalType("Image")}),
        consumes=frozenset({SignalType("TriggerIn")}),
    )


@pytest.mark.unit
def test_evolve_role_defined_sets_genesis_fields() -> None:
    state = evolve(None, _defined())
    assert state.id == RoleId(_ROLE_ID)
    assert state.name == RoleName("Imager")
    assert state.docstring == "Acquires 2D image frames on exposure or trigger."
    assert state.required_affordances == frozenset({Affordance.IMAGEABLE})
    assert state.optional_affordances == frozenset({Affordance.BINNABLE})
    assert state.produces == frozenset({SignalType("Image")})
    assert state.consumes == frozenset({SignalType("TriggerIn")})


@pytest.mark.unit
def test_evolve_role_defined_ignores_prior_state() -> None:
    """Genesis arm: prior state is replaced wholesale (defensive evolver
    semantic; matches `FamilyDefined` precedent)."""
    prior = evolve(None, _defined())
    overridden = evolve(prior, replace(_defined(), name="Different"))
    assert overridden.name == RoleName("Different")


@pytest.mark.unit
def test_fold_empty_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_role_defined_returns_state() -> None:
    state = fold([_defined()])
    assert state is not None
    assert state.id == RoleId(_ROLE_ID)


@pytest.mark.unit
def test_to_payload_round_trip_via_stored() -> None:
    original = _defined()
    payload = to_payload(original)
    stored = StoredEvent(
        event_id=_EVENT_ID,
        event_type=event_type_name(original),
        stream_type="Role",
        stream_id=_ROLE_ID,
        version=1,
        position=1,
        occurred_at=_NOW,
        payload=payload,
        schema_version=1,
        correlation_id=_CORR,
        causation_id=None,
        principal_id=_PRINC,
        metadata={"command": "DefineRole"},
        recorded_at=_NOW,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_to_payload_sorts_collections_for_deterministic_serialization() -> None:
    event = replace(
        _defined(),
        produces=frozenset({SignalType("Zeta"), SignalType("Alpha")}),
        required_affordances=frozenset({Affordance.STREAMABLE, Affordance.IMAGEABLE}),
    )
    payload = to_payload(event)
    assert payload["produces"] == ["Alpha", "Zeta"]
    assert payload["required_affordances"] == sorted(payload["required_affordances"])


@pytest.mark.unit
def test_from_stored_unknown_event_type_raises_value_error() -> None:
    stored = StoredEvent(
        event_id=_EVENT_ID,
        event_type="RoleSomethingElse",
        stream_type="Role",
        stream_id=_ROLE_ID,
        version=1,
        position=1,
        occurred_at=_NOW,
        payload={},
        schema_version=1,
        correlation_id=_CORR,
        causation_id=None,
        principal_id=_PRINC,
        metadata={},
        recorded_at=_NOW,
    )
    with pytest.raises(ValueError, match="Unknown RoleEvent event_type"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_malformed_payload_raises_value_error() -> None:
    """Defensive: a `RoleDefined` payload missing required keys surfaces
    as `Malformed RoleDefined` via `deserialize_or_raise`."""
    stored = StoredEvent(
        event_id=_EVENT_ID,
        event_type="RoleDefined",
        stream_type="Role",
        stream_id=_ROLE_ID,
        version=1,
        position=1,
        occurred_at=_NOW,
        payload={"role_id": str(_ROLE_ID)},  # missing name / docstring / occurred_at
        schema_version=1,
        correlation_id=_CORR,
        causation_id=None,
        principal_id=_PRINC,
        metadata={},
        recorded_at=_NOW,
    )
    with pytest.raises(ValueError, match="Malformed RoleDefined"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_tolerates_missing_optional_collection_fields() -> None:
    """Additive-state pattern: a payload predating an additive field
    defaults to an empty collection (mirrors FamilyDefined affordances)."""
    payload = {
        "role_id": str(_ROLE_ID),
        "name": "Imager",
        "docstring": "x",
        "occurred_at": _NOW.isoformat(),
    }
    stored = StoredEvent(
        event_id=_EVENT_ID,
        event_type="RoleDefined",
        stream_type="Role",
        stream_id=_ROLE_ID,
        version=1,
        position=1,
        occurred_at=_NOW,
        payload=payload,
        schema_version=1,
        correlation_id=_CORR,
        causation_id=None,
        principal_id=_PRINC,
        metadata={},
        recorded_at=_NOW,
    )
    rebuilt = from_stored(stored)
    assert rebuilt.required_affordances == frozenset()
    assert rebuilt.optional_affordances == frozenset()
    assert rebuilt.produces == frozenset()
    assert rebuilt.consumes == frozenset()


@pytest.mark.unit
def test_from_stored_unknown_affordance_value_raises_value_error() -> None:
    """Defensive: unknown Affordance value strings fail loud (StrEnum
    constructor mirrors Family's `_load_affordances` posture)."""
    payload = {
        "role_id": str(_ROLE_ID),
        "name": "Imager",
        "docstring": "x",
        "occurred_at": _NOW.isoformat(),
        "required_affordances": ["NotARealAffordance"],
        "optional_affordances": [],
        "produces": [],
        "consumes": [],
    }
    stored = StoredEvent(
        event_id=_EVENT_ID,
        event_type="RoleDefined",
        stream_type="Role",
        stream_id=_ROLE_ID,
        version=1,
        position=1,
        occurred_at=_NOW,
        payload=payload,
        schema_version=1,
        correlation_id=_CORR,
        causation_id=None,
        principal_id=_PRINC,
        metadata={},
        recorded_at=_NOW,
    )
    with pytest.raises(ValueError, match="Malformed RoleDefined"):
        from_stored(stored)


def _stored_role_defined(role_id: UUID, name: str = "X") -> StoredEvent:
    payload = to_payload(
        RoleDefined(
            role_id=role_id,
            name=name,
            docstring="x",
            occurred_at=_NOW,
        )
    )
    return StoredEvent(
        event_id=uuid4(),
        event_type="RoleDefined",
        stream_type="Role",
        stream_id=role_id,
        version=1,
        position=1,
        occurred_at=_NOW,
        payload=payload,
        schema_version=1,
        correlation_id=_CORR,
        causation_id=None,
        principal_id=_PRINC,
        metadata={"command": "DefineRole"},
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_fold_round_trip_through_stored() -> None:
    """End-to-end: a `RoleDefined` event round-trips through
    `to_payload` -> `StoredEvent` -> `from_stored` -> `evolve` ->
    `Role` with no data loss."""
    role_id = uuid4()
    stored = _stored_role_defined(role_id, name="Conditioner")
    rebuilt = from_stored(stored)
    state = evolve(None, rebuilt)
    assert state.id == RoleId(role_id)
    assert state.name == RoleName("Conditioner")
