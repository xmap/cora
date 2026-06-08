"""SupplyEvent serialization round-trips: to_payload + from_stored.

Every Supply event carries a `trigger` + `triggered_by` discriminated-
union pair on its payload per [[project_fold_symmetry_design]]. The
serializer drops them into the JSON payload as `trigger` (string) and
`triggered_by` (UUID string); `from_stored` re-wraps the UUID in the
NewType implied by `trigger` (ActorId / MonitorSourceId / SchedulerTickId).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId, MonitorSourceId, SchedulerTickId
from cora.supply.aggregates.supply import (
    SupplyDegraded,
    SupplyDeregistered,
    SupplyMarkedAvailable,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyRegistered,
    SupplyRestored,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005111")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000005222"))
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-000000005333"))
_SCHEDULER_TICK_ID = SchedulerTickId(UUID("01900000-0000-7000-8000-000000005444"))


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Supply",
        stream_id=_SUPPLY_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- SupplyRegistered ----------


@pytest.mark.unit
def test_supply_registered_event_type_name() -> None:
    event = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="2-BM LN2 drop",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "SupplyRegistered"


@pytest.mark.unit
def test_supply_registered_to_payload() -> None:
    event = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="2-BM LN2 drop",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "supply_id": str(_SUPPLY_ID),
        "scope": "Beamline",
        "kind": "LiquidNitrogen",
        "name": "2-BM LN2 drop",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_supply_registered_round_trip_via_from_stored() -> None:
    original = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Facility",
        kind="PhotonBeam",
        name="APS storage-ring beam",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("SupplyRegistered", to_payload(original)))
    assert rebuilt == original


# ---------- SupplyMarkedAvailable ----------


@pytest.mark.unit
def test_supply_marked_available_event_type_name() -> None:
    event = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="operator walkdown",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "SupplyMarkedAvailable"


@pytest.mark.unit
def test_supply_marked_available_to_payload() -> None:
    event = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="operator walkdown",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Unknown",
        "reason": "operator walkdown",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_supply_marked_available_round_trip_via_from_stored() -> None:
    original = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="operator confirms beam delivered after morning startup",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("SupplyMarkedAvailable", to_payload(original)))
    assert rebuilt == original


# ---------- from_stored unknown event_type ----------


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown SupplyEvent event_type"):
        from_stored(_stored("ImaginaryEvent", {"foo": "bar"}))


# ---------- 10a-b transition events: round-trips ----------


@pytest.mark.parametrize(
    ("event_class", "expected_type_name"),
    [
        (SupplyDegraded, "SupplyDegraded"),
        (SupplyMarkedUnavailable, "SupplyMarkedUnavailable"),
        (SupplyMarkedRecovering, "SupplyMarkedRecovering"),
        (SupplyRestored, "SupplyRestored"),
        (SupplyDeregistered, "SupplyDeregistered"),
    ],
)
@pytest.mark.unit
def test_transition_event_type_name(event_class: Any, expected_type_name: str) -> None:
    """All 5 transition event classes (4 FSM-closure + lifecycle-terminal
    Deregistered) report their own class name via event_type_name (the
    discriminator written into StoredEvent.event_type)."""
    event = event_class(
        supply_id=_SUPPLY_ID,
        from_status="x",
        reason="r",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == expected_type_name


@pytest.mark.parametrize(
    "event_class",
    [
        SupplyDegraded,
        SupplyMarkedUnavailable,
        SupplyMarkedRecovering,
        SupplyRestored,
        SupplyDeregistered,
    ],
)
@pytest.mark.unit
def test_transition_event_to_payload_carries_audit_quad(
    event_class: Any,
) -> None:
    """All 5 transition events share the same payload shape (`from_status`,
    `reason`, `trigger`, `triggered_by`, `occurred_at`); pin the serialization."""
    event = event_class(
        supply_id=_SUPPLY_ID,
        from_status="Available",
        reason="ops gesture",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Available",
        "reason": "ops gesture",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.parametrize(
    ("event_class", "event_type_str"),
    [
        (SupplyDegraded, "SupplyDegraded"),
        (SupplyMarkedUnavailable, "SupplyMarkedUnavailable"),
        (SupplyMarkedRecovering, "SupplyMarkedRecovering"),
        (SupplyRestored, "SupplyRestored"),
        (SupplyDeregistered, "SupplyDeregistered"),
    ],
)
@pytest.mark.unit
def test_transition_event_round_trip_via_from_stored(event_class: Any, event_type_str: str) -> None:
    """Round-trip each transition event class through to_payload + from_stored
    and verify equality. Pins the per-event-type dispatch in `from_stored`."""
    original = event_class(
        supply_id=_SUPPLY_ID,
        from_status="Available",
        reason="ops gesture",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored(event_type_str, to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "SupplyRegistered",
        "SupplyMarkedAvailable",
        "SupplyDegraded",
        "SupplyMarkedUnavailable",
        "SupplyMarkedRecovering",
        "SupplyRestored",
        "SupplyDeregistered",
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


# ---------- trigger / triggered_by pairing invariant ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("trigger", "triggered_by"),
    [
        ("Operator", _ACTOR_ID),
        ("Monitor", _MONITOR_SOURCE_ID),
        ("Auto", _SCHEDULER_TICK_ID),
    ],
)
def test_event_accepts_every_trigger_to_typed_id_pairing(trigger: str, triggered_by: Any) -> None:
    """Every (trigger, triggered_by-tier) pairing constructs cleanly:
    Operator/ActorId, Monitor/MonitorSourceId, Auto/SchedulerTickId.
    The NewType wrappers are erased at runtime so the union is
    structurally a UUID; the typed identity is preserved at the
    static type-check site."""
    event = SupplyDegraded(
        supply_id=_SUPPLY_ID,
        from_status="Available",
        reason="r",
        trigger=trigger,
        triggered_by=triggered_by,
        occurred_at=_NOW,
    )
    assert event.trigger == trigger
    assert event.triggered_by == triggered_by


@pytest.mark.unit
def test_event_rejects_unknown_trigger_string() -> None:
    """The `__post_init__` invariant rejects any trigger string outside
    the locked 3-value enum so callers can never persist a malformed
    trigger discriminator."""
    with pytest.raises(ValueError, match="trigger must be one of Operator"):
        SupplyDegraded(
            supply_id=_SUPPLY_ID,
            from_status="Available",
            reason="r",
            trigger="Mystery",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )


@pytest.mark.unit
def test_event_rejects_non_uuid_triggered_by() -> None:
    """`triggered_by` must be UUID-shaped (NewType identity); a bare
    string fails the construction invariant before the event leaves
    the decider."""
    with pytest.raises(TypeError, match="triggered_by must be a UUID-shaped"):
        SupplyDegraded(
            supply_id=_SUPPLY_ID,
            from_status="Available",
            reason="r",
            trigger="Operator",
            triggered_by="not-a-uuid",  # pyright: ignore[reportArgumentType]
            occurred_at=_NOW,
        )
