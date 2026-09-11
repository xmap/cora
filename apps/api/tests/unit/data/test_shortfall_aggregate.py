"""Shortfall aggregate: the write side and the read side agree.

`ingest_scan` only ever APPENDS a Shortfall, so nothing in the slice's
own tests ever folds one back. That leaves `from_stored`, `evolve`,
`fold` and `load_shortfall` written but unexercised, which in an
event-sourced system is a latent bug rather than a coverage statistic:
an event that cannot be read back is an event that is not really
recorded. `test_event_union_from_stored_coverage.py` does not close
this either, since it skips single-event aggregates, which is exactly
this shape.

The round trip asserts the WHOLE folded state against an explicitly
constructed `Shortfall`, not field by field. A per-field assertion is
blind to a field the writer forgot to carry, because the reader's
default quietly fills it in (see [[project_field_drop_bug_class]]);
comparing the whole dataclass fails the moment `to_payload` /
`from_stored` / `evolve` drop one between them.
"""

from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.shortfall import (
    Shortfall,
    ShortfallReason,
    ShortfallRecorded,
    ShortfallStatus,
    event_type_name,
    from_stored,
    load_shortfall,
    shortfall_stream_id,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

pytestmark = pytest.mark.unit

_CAPTURE_PATH_ID = UUID("01900000-0000-7000-8000-0000000091a1")
_RUN_ID = UUID("01900000-0000-7000-8000-0000000091b2")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-0000000091c3"))

_FILE_MODIFIED_AT = datetime(2026, 7, 29, 14, 59, 52, tzinfo=UTC)
_RUN_ENDED_AT = datetime(2026, 7, 29, 15, 0, 0, tzinfo=UTC)
_RECORDED_AT = datetime(2026, 7, 29, 16, 0, 0, tzinfo=UTC)


def _recorded(**overrides: object) -> ShortfallRecorded:
    values: dict[str, object] = {
        "shortfall_id": shortfall_stream_id(_CAPTURE_PATH_ID),
        "producing_run_id": _RUN_ID,
        "capture_path_id": _CAPTURE_PATH_ID,
        "host": "tomdet",
        "root": "/local1/2BM",
        "projection_count": 1,
        "commanded_projection_count": 1541,
        "dropped_frame_count": 3,
        "reason": ShortfallReason.STRUCTURALLY_INCOMPLETE,
        "file_modified_at": _FILE_MODIFIED_AT,
        "run_ended_at": _RUN_ENDED_AT,
        "occurred_at": _RECORDED_AT,
        "recorded_by": _ACTOR_ID,
    }
    values.update(overrides)
    return ShortfallRecorded(**values)  # type: ignore[arg-type]


def _stored(event: ShortfallRecorded) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Shortfall",
        stream_id=event.shortfall_id,
        version=1,
        event_type=event_type_name(event),
        schema_version=1,
        payload=to_payload(event),
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=event.occurred_at,
        recorded_at=event.occurred_at,
    )


async def _append(store: InMemoryEventStore, event: ShortfallRecorded) -> None:
    await store.append(
        stream_type="Shortfall",
        stream_id=event.shortfall_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid4(),
                command_name="IngestScan",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=UUID(str(_ACTOR_ID)),
            )
        ],
    )


async def test_a_recorded_shortfall_folds_back_to_the_state_that_was_written() -> None:
    store = InMemoryEventStore()
    event = _recorded()
    await _append(store, event)

    loaded = await load_shortfall(store, event.shortfall_id)

    assert loaded == Shortfall(
        id=event.shortfall_id,
        producing_run_id=_RUN_ID,
        capture_path_id=_CAPTURE_PATH_ID,
        host="tomdet",
        root="/local1/2BM",
        projection_count=1,
        commanded_projection_count=1541,
        dropped_frame_count=3,
        reason=ShortfallReason.STRUCTURALLY_INCOMPLETE,
        file_modified_at=_FILE_MODIFIED_AT,
        run_ended_at=_RUN_ENDED_AT,
        recorded_at=_RECORDED_AT,
        recorded_by=_ACTOR_ID,
        status=ShortfallStatus.RECORDED,
    )


async def test_loading_a_stream_that_holds_nothing_returns_none() -> None:
    store = InMemoryEventStore()
    assert await load_shortfall(store, shortfall_stream_id(_CAPTURE_PATH_ID)) is None


def test_absent_counts_survive_the_round_trip_as_none_not_zero() -> None:
    """A file that records no commanded total is UNQUANTIFIED, which is
    a different fact from one that commanded zero frames. Serializing
    None to null and back has to preserve that."""
    event = _recorded(commanded_projection_count=None, dropped_frame_count=None)

    payload = to_payload(event)
    assert payload["commanded_projection_count"] is None
    assert payload["dropped_frame_count"] is None

    assert from_stored(_stored(event)) == event


def test_the_closed_reason_survives_the_round_trip_as_the_enum() -> None:
    """The payload carries the string value, and the reader has to hand
    back the enum member: a bare string here would defeat the closed
    vocabulary the whole design rests on."""
    event = _recorded()
    assert to_payload(event)["reason"] == "StructurallyIncomplete"

    rebuilt = from_stored(_stored(event))
    assert rebuilt.reason is ShortfallReason.STRUCTURALLY_INCOMPLETE


def test_a_foreign_event_type_on_the_stream_is_refused_loudly() -> None:
    """A stream contaminated with another aggregate's event must fail
    the fold rather than be silently skipped, or the state that comes
    back is quietly wrong."""
    # `replace` rather than a second constructor call: a hand-rebuilt
    # StoredEvent silently stops tracking new fields on that dataclass.
    contaminated = dc_replace(_stored(_recorded()), event_type="AcquisitionRecorded")

    with pytest.raises(ValueError, match="Unknown ShortfallEvent event_type"):
        from_stored(contaminated)


def test_the_stream_id_derives_from_the_capture_path_and_nothing_else() -> None:
    """Determinism is what makes `expected_version=0` the dedupe rather
    than a projection read, and the seed is the opaque surrogate so the
    id can never be a confirmation oracle for a guessed path."""
    again = shortfall_stream_id(_CAPTURE_PATH_ID)
    other = shortfall_stream_id(UUID("01900000-0000-7000-8000-0000000091ff"))

    assert again == shortfall_stream_id(_CAPTURE_PATH_ID)
    assert again != other
