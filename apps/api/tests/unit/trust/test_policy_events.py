"""Unit tests for the Policy aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    PolicyGrantRevoked,
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
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Policy",
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
    event = PolicyDefined(
        policy_id=uuid4(),
        name="X",
        conduit_id=uuid4(),
        permitted_principal_ids=(),
        permitted_commands=(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PolicyDefined"


@pytest.mark.unit
def test_to_payload_serializes_policy_defined_to_primitives() -> None:
    policy_id = uuid4()
    conduit = uuid4()
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    event = PolicyDefined(
        policy_id=policy_id,
        name="Beam-team",
        conduit_id=conduit,
        permitted_principal_ids=(p1,),
        permitted_commands=("RegisterActor",),
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "policy_id": str(policy_id),
        "name": "Beam-team",
        "conduit_id": str(conduit),
        # for V1-shape callers. V1 events on disk lack the field and fold
        # via `from_stored`'s `.get(..., nil)` default.
        "surface_id": "00000000-0000-0000-0000-000000000000",
        "permitted_principal_ids": [str(p1)],
        "permitted_commands": ["RegisterActor"],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_sorts_permission_lists_deterministically() -> None:
    """Same logical permission set should produce same payload bytes
    regardless of input ordering (matters for idempotency-key hashing
    and content-addressed lookups). Permission sets serialize sorted
    by string form."""
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    p2 = UUID("01900000-0000-7000-8000-000000000222")
    p3 = UUID("01900000-0000-7000-8000-000000000333")

    event_in_one_order = PolicyDefined(
        policy_id=uuid4(),
        name="X",
        conduit_id=uuid4(),
        permitted_principal_ids=(p3, p1, p2),
        permitted_commands=("Z", "A", "M"),
        occurred_at=_NOW,
    )
    payload = to_payload(event_in_one_order)

    assert payload["permitted_principal_ids"] == sorted([str(p1), str(p2), str(p3)])
    assert payload["permitted_commands"] == ["A", "M", "Z"]


@pytest.mark.unit
def test_from_stored_rebuilds_policy_defined() -> None:
    policy_id = uuid4()
    conduit = uuid4()
    p1 = uuid4()
    stored = _stored(
        "PolicyDefined",
        {
            "policy_id": str(policy_id),
            "name": "Beam-team",
            "conduit_id": str(conduit),
            "permitted_principal_ids": [str(p1)],
            "permitted_commands": ["RegisterActor"],
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PolicyDefined(
        policy_id=policy_id,
        name="Beam-team",
        conduit_id=conduit,
        permitted_principal_ids=(p1,),
        permitted_commands=("RegisterActor",),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for the (de)serialization pair."""
    original = PolicyDefined(
        policy_id=uuid4(),
        name="Beam-team",
        conduit_id=uuid4(),
        permitted_principal_ids=(uuid4(), uuid4()),
        permitted_commands=("X", "Y"),
        occurred_at=_NOW,
    )
    stored = _stored("PolicyDefined", to_payload(original))
    rebuilt = from_stored(stored)
    # Lists may differ in order after sort+rebuild; compare as sets.
    assert isinstance(rebuilt, PolicyDefined)
    assert rebuilt.policy_id == original.policy_id
    assert rebuilt.name == original.name
    assert rebuilt.conduit_id == original.conduit_id
    assert set(rebuilt.permitted_principal_ids) == set(original.permitted_principal_ids)
    assert set(rebuilt.permitted_commands) == set(original.permitted_commands)
    assert rebuilt.occurred_at == original.occurred_at


@pytest.mark.unit
def test_event_type_name_returns_grant_revoked_class_name() -> None:
    event = PolicyGrantRevoked(
        policy_id=uuid4(),
        principal_id=uuid4(),
        revoked_by=uuid4(),
        reason="access review",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PolicyGrantRevoked"


@pytest.mark.unit
def test_to_payload_serializes_grant_revoked_to_primitives() -> None:
    policy_id = uuid4()
    principal_id = uuid4()
    revoked_by = uuid4()
    event = PolicyGrantRevoked(
        policy_id=policy_id,
        principal_id=principal_id,
        revoked_by=revoked_by,
        reason="access review",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "policy_id": str(policy_id),
        "principal_id": str(principal_id),
        "revoked_by": str(revoked_by),
        "reason": "access review",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_grant_revoked_to_payload_then_from_stored_round_trips() -> None:
    original = PolicyGrantRevoked(
        policy_id=uuid4(),
        principal_id=uuid4(),
        revoked_by=uuid4(),
        reason="access review",
        occurred_at=_NOW,
    )
    stored = _stored("PolicyGrantRevoked", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud."""
    stored = _stored("ZoneDefined", {})
    with pytest.raises(ValueError, match="Unknown PolicyEvent event_type"):
        from_stored(stored)


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`.


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "PolicyDefined",
        "PolicyGrantRevoked",
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
