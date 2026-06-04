"""Unit tests for the Method aggregate's event (de)serialization helpers.

`needed_family_ids` is the first event-payload field in Recipe
that uses the list-in-payload-frozenset-in-state pattern (precedent
from Trust's Policy). Pinned: payload sorted by UUID string form
for determinism (idempotency-key hashing relies on it).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodParametersSchemaUpdated,
    MethodVersioned,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell — only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Method",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = MethodDefined(
        method_id=uuid4(),
        name="XRF Mapping",
        needed_family_ids=(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "MethodDefined"


@pytest.mark.unit
def test_to_payload_serializes_method_defined_to_primitives() -> None:
    method_id = uuid4()
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    event = MethodDefined(
        method_id=method_id,
        name="XRF Fly Mapping",
        needed_family_ids=(cap1,),
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "method_id": str(method_id),
        "name": "XRF Fly Mapping",
        "needed_family_ids": [str(cap1)],
        # needed_supplies (default factory). Sorted lexically when
        # populated; pinned by tests/unit/recipe/test_method_needed_supplies.py.
        "needed_supplies": [],
        # (default). 6l-strict will require the field on the command;
        # the payload key stays additive for stream-replay compat.
        "capability_id": None,
        # needed_assembly_ids (default factory). Sorted by UUID string when
        # populated; pinned by tests/unit/recipe/test_method_needed_assembly_ids.py.
        "needed_assembly_ids": [],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_handles_empty_needed_family_ids() -> None:
    """Procedural Methods (for example, 'Sample Cleaning') need no specific
    Family; payload's needed_family_ids is `[]`. Pinned because
    a future change that omits the field on empty would break the
    fold-on-read contract."""
    method_id = uuid4()
    event = MethodDefined(
        method_id=method_id,
        name="Sample Cleaning",
        needed_family_ids=(),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["needed_family_ids"] == []


@pytest.mark.unit
def test_to_payload_sorts_needed_family_ids_deterministically() -> None:
    """Same logical capability set must produce same payload bytes
    regardless of input ordering. Critical for idempotency-key hashing
    (Stripe-style replay returns cached result only when bodies match
    byte-for-byte after canonical normalization). Locks the same
    convention as Trust's PolicyDefined.permitted_principal_ids sorting."""
    c1 = UUID("01900000-0000-7000-8000-000000000111")
    c2 = UUID("01900000-0000-7000-8000-000000000222")
    c3 = UUID("01900000-0000-7000-8000-000000000333")

    event_in_one_order = MethodDefined(
        method_id=uuid4(),
        name="X",
        needed_family_ids=(c3, c1, c2),
        occurred_at=_NOW,
    )
    payload = to_payload(event_in_one_order)

    assert payload["needed_family_ids"] == sorted([str(c1), str(c2), str(c3)])


@pytest.mark.unit
def test_from_stored_rebuilds_method_defined() -> None:
    method_id = uuid4()
    cap1 = uuid4()
    cap2 = uuid4()
    stored = _stored(
        "MethodDefined",
        {
            "method_id": str(method_id),
            "name": "XRF Fly Mapping",
            "needed_family_ids": sorted([str(cap1), str(cap2)]),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    assert rebuilt.method_id == method_id
    assert rebuilt.name == "XRF Fly Mapping"
    assert set(rebuilt.needed_family_ids) == {cap1, cap2}


@pytest.mark.unit
def test_from_stored_handles_empty_needed_family_ids() -> None:
    method_id = uuid4()
    stored = _stored(
        "MethodDefined",
        {
            "method_id": str(method_id),
            "name": "Sample Cleaning",
            "needed_family_ids": [],
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    assert rebuilt.needed_family_ids == ()


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each
    other's inverse for the typical (with capabilities) case."""
    cap1 = uuid4()
    cap2 = uuid4()
    original = MethodDefined(
        method_id=uuid4(),
        name="XRF Fly Mapping",
        needed_family_ids=(cap1, cap2),
        occurred_at=_NOW,
    )
    stored = _stored("MethodDefined", to_payload(original))
    rebuilt = from_stored(stored)
    # Order may differ (payload sorted; original input order preserved
    # in event), so compare as sets.
    assert isinstance(rebuilt, MethodDefined)
    assert rebuilt.method_id == original.method_id
    assert rebuilt.name == original.name
    assert set(rebuilt.needed_family_ids) == set(original.needed_family_ids)
    assert rebuilt.occurred_at == original.occurred_at


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("FamilyDefined", {})
    with pytest.raises(ValueError, match="Unknown MethodEvent event_type"):
        from_stored(stored)


# ---------- MethodVersioned ----------


@pytest.mark.unit
def test_event_type_name_returns_method_versioned_class_name() -> None:
    event = MethodVersioned(method_id=uuid4(), version_tag="v2", occurred_at=_NOW)
    assert event_type_name(event) == "MethodVersioned"


@pytest.mark.unit
def test_to_payload_serializes_method_versioned_with_version_tag() -> None:
    method_id = uuid4()
    event = MethodVersioned(method_id=method_id, version_tag="2026-Q3", occurred_at=_NOW)
    assert to_payload(event) == {
        "method_id": str(method_id),
        "version_tag": "2026-Q3",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_method_versioned() -> None:
    method_id = uuid4()
    stored = _stored(
        "MethodVersioned",
        {
            "method_id": str(method_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_method_versioned() -> None:
    original = MethodVersioned(method_id=uuid4(), version_tag="v3", occurred_at=_NOW)
    stored = _stored("MethodVersioned", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_content_hash_when_present() -> None:
    """Content-hash adoption (Candidate A): the decider attaches a
    64-char hex; the payload carries it under `content_hash` so
    downstream consumers (projection, RO-Crate export, etag) can
    read it without re-folding the stream."""
    method_id = uuid4()
    h = "a" * 64
    event = MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW, content_hash=h)
    payload = to_payload(event)
    assert payload["content_hash"] == h


@pytest.mark.unit
def test_to_payload_omits_content_hash_when_none() -> None:
    """Pre-rollout / dataclass-default events serialize without the
    `content_hash` key so the persisted payload bytes match what
    pre-Candidate-A streams already contain. Critical for
    projection-replay determinism."""
    event = MethodVersioned(method_id=uuid4(), version_tag="v2", occurred_at=_NOW)
    payload = to_payload(event)
    assert "content_hash" not in payload


@pytest.mark.unit
def test_from_stored_loads_content_hash_when_present() -> None:
    method_id = uuid4()
    h = "b" * 64
    stored = _stored(
        "MethodVersioned",
        {
            "method_id": str(method_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
            "content_hash": h,
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodVersioned)
    assert rebuilt.content_hash == h


@pytest.mark.unit
def test_from_stored_defaults_content_hash_to_none_for_pre_rollout_payload() -> None:
    """Pre-Candidate-A MethodVersioned events have no `content_hash`
    field; from_stored substitutes None so the evolver's fold stays
    deterministic and Method.content_hash ends up None for legacy
    revisions. Additive-evolution pattern per
    [[project_content_addressed_identity_design]]."""
    method_id = uuid4()
    stored = _stored(
        "MethodVersioned",
        {
            "method_id": str(method_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodVersioned)
    assert rebuilt.content_hash is None


@pytest.mark.unit
def test_round_trip_with_content_hash_preserved() -> None:
    h = "c" * 64
    original = MethodVersioned(
        method_id=uuid4(), version_tag="v2", occurred_at=_NOW, content_hash=h
    )
    stored = _stored("MethodVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- MethodDeprecated ----------


@pytest.mark.unit
def test_event_type_name_returns_method_deprecated_class_name() -> None:
    event = MethodDeprecated(method_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "MethodDeprecated"


@pytest.mark.unit
def test_to_payload_serializes_method_deprecated_to_primitives() -> None:
    """Status NOT in payload — event TYPE encodes the state change."""
    method_id = uuid4()
    event = MethodDeprecated(method_id=method_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "method_id": str(method_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_method_deprecated() -> None:
    method_id = uuid4()
    stored = _stored(
        "MethodDeprecated",
        {
            "method_id": str(method_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == MethodDeprecated(method_id=method_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_method_deprecated() -> None:
    original = MethodDeprecated(method_id=uuid4(), occurred_at=_NOW)
    stored = _stored("MethodDeprecated", to_payload(original))
    assert from_stored(stored) == original


# ---------- MethodParametersSchemaUpdated ----------


_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_SAMPLE_SCHEMA = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
}


@pytest.mark.unit
def test_event_type_name_returns_parameters_schema_updated_class_name() -> None:
    event = MethodParametersSchemaUpdated(
        method_id=uuid4(), parameters_schema=_SAMPLE_SCHEMA, occurred_at=_NOW
    )
    assert event_type_name(event) == "MethodParametersSchemaUpdated"


@pytest.mark.unit
def test_to_payload_serializes_parameters_schema_updated_with_dict() -> None:
    method_id = uuid4()
    event = MethodParametersSchemaUpdated(
        method_id=method_id, parameters_schema=_SAMPLE_SCHEMA, occurred_at=_NOW
    )
    assert to_payload(event) == {
        "method_id": str(method_id),
        "parameters_schema": _SAMPLE_SCHEMA,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_parameters_schema_updated_with_none() -> None:
    """Clearing the schema serializes parameters_schema=null. Pinned
    so a future change can't drop the key (the projection's
    `payload.get("parameters_schema") is not None` would silently
    keep the present-flag at TRUE)."""
    method_id = uuid4()
    event = MethodParametersSchemaUpdated(
        method_id=method_id, parameters_schema=None, occurred_at=_NOW
    )
    payload = to_payload(event)
    assert payload["parameters_schema"] is None
    assert "parameters_schema" in payload


@pytest.mark.unit
def test_from_stored_rebuilds_parameters_schema_updated_with_dict() -> None:
    method_id = uuid4()
    stored = _stored(
        "MethodParametersSchemaUpdated",
        {
            "method_id": str(method_id),
            "parameters_schema": _SAMPLE_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == MethodParametersSchemaUpdated(
        method_id=method_id, parameters_schema=_SAMPLE_SCHEMA, occurred_at=_NOW
    )


@pytest.mark.unit
def test_from_stored_rebuilds_parameters_schema_updated_with_none() -> None:
    method_id = uuid4()
    stored = _stored(
        "MethodParametersSchemaUpdated",
        {
            "method_id": str(method_id),
            "parameters_schema": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == MethodParametersSchemaUpdated(
        method_id=method_id, parameters_schema=None, occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_parameters_schema_updated() -> None:
    original = MethodParametersSchemaUpdated(
        method_id=uuid4(), parameters_schema=_SAMPLE_SCHEMA, occurred_at=_NOW
    )
    stored = _stored("MethodParametersSchemaUpdated", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "MethodDefined",
        "MethodVersioned",
        "MethodDeprecated",
        "MethodParametersSchemaUpdated",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Per the convention adopted post-corpus-survey (Marten /
    pyeventsourcing / Pydantic / msgspec all wrap), each event-type case
    wraps `KeyError`/`TypeError`/`AttributeError` into a tagged
    `ValueError` so a corrupted event row fails loud with the event-type
    name in the message rather than bubbling a raw KeyError from deep
    in the load path."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))
