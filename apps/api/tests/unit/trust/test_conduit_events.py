"""Unit tests for the Conduit aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust.aggregates.conduit.events import (
    ConduitDefined,
    ConduitLogbookClosed,
    ConduitLogbookOpened,
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
        stream_type="Conduit",
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
    event = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ConduitDefined"


@pytest.mark.unit
def test_to_payload_serializes_conduit_defined_to_primitives() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    event = ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "conduit_id": str(conduit_id),
        "name": "Detector-to-Storage",
        "source_zone_id": str(source),
        "target_zone_id": str(target),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_defined() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    stored = _stored(
        "ConduitDefined",
        {
            "conduit_id": str(conduit_id),
            "name": "Detector-to-Storage",
            "source_zone_id": str(source),
            "target_zone_id": str(target),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("ConduitDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ZoneDefined", {})
    with pytest.raises(ValueError, match="Unknown ConduitEvent event_type"):
        from_stored(stored)


# ---------- ConduitLogbookOpened ----------


def _sample_schema() -> LogbookSchema:
    return LogbookSchema(
        fields={
            "actor_id": LogbookFieldSpec(type="uuid"),
            "command_name": LogbookFieldSpec(type="string"),
        },
        description="auth audit log",
    )


@pytest.mark.unit
def test_event_type_name_for_conduit_logbook_opened() -> None:
    event = ConduitLogbookOpened(
        conduit_id=uuid4(),
        logbook_id=uuid4(),
        kind="traversals",
        schema=_sample_schema(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ConduitLogbookOpened"


@pytest.mark.unit
def test_to_payload_serializes_logbook_opened_with_schema_dict() -> None:
    conduit_id = uuid4()
    logbook_id = uuid4()
    schema = _sample_schema()
    event = ConduitLogbookOpened(
        conduit_id=conduit_id,
        logbook_id=logbook_id,
        kind="traversals",
        schema=schema,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "conduit_id": str(conduit_id),
        "logbook_id": str(logbook_id),
        "kind": "traversals",
        "schema": schema.to_dict(),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_logbook_opened() -> None:
    conduit_id = uuid4()
    logbook_id = uuid4()
    schema = _sample_schema()
    stored = _stored(
        "ConduitLogbookOpened",
        {
            "conduit_id": str(conduit_id),
            "logbook_id": str(logbook_id),
            "kind": "traversals",
            "schema": schema.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitLogbookOpened(
        conduit_id=conduit_id,
        logbook_id=logbook_id,
        kind="traversals",
        schema=schema,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_conduit_logbook_opened_round_trips() -> None:
    original = ConduitLogbookOpened(
        conduit_id=uuid4(),
        logbook_id=uuid4(),
        kind="traversals",
        schema=_sample_schema(),
        occurred_at=_NOW,
    )
    stored = _stored("ConduitLogbookOpened", to_payload(original))
    assert from_stored(stored) == original


# ---------- ConduitLogbookClosed ----------


@pytest.mark.unit
def test_event_type_name_for_conduit_logbook_closed() -> None:
    event = ConduitLogbookClosed(conduit_id=uuid4(), logbook_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "ConduitLogbookClosed"


@pytest.mark.unit
def test_to_payload_serializes_logbook_closed_to_primitives() -> None:
    conduit_id = uuid4()
    logbook_id = uuid4()
    event = ConduitLogbookClosed(conduit_id=conduit_id, logbook_id=logbook_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "conduit_id": str(conduit_id),
        "logbook_id": str(logbook_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_logbook_closed() -> None:
    conduit_id = uuid4()
    logbook_id = uuid4()
    stored = _stored(
        "ConduitLogbookClosed",
        {
            "conduit_id": str(conduit_id),
            "logbook_id": str(logbook_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitLogbookClosed(
        conduit_id=conduit_id, logbook_id=logbook_id, occurred_at=_NOW
    )


@pytest.mark.unit
def test_conduit_logbook_closed_round_trips() -> None:
    original = ConduitLogbookClosed(conduit_id=uuid4(), logbook_id=uuid4(), occurred_at=_NOW)
    stored = _stored("ConduitLogbookClosed", to_payload(original))
    assert from_stored(stored) == original


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`. Handler-level tests
# (`test_define_conduit_handler`, integration / contract tests)
# verify the envelope shape end-to-end against a real event store.


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "ConduitDefined",
        "ConduitLogbookOpened",
        "ConduitLogbookClosed",
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
