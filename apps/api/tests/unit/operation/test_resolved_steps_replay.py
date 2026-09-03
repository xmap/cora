"""Unit tests for the resolved-steps replay finder.

The resume path replays a halted conduct from the `ResolvedStepsRecorded`
event pinned at conduct start. `find_resolved_steps_record` locates it.

These pin OBSERVED behaviour, not desired behaviour. The finder shipped
with no coverage, and its docstring asserted a stream invariant that the
emitting decider does not enforce, so what it does with a duplicate pin is
recorded here rather than endorsed.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation._recipe_expansion import find_resolved_steps_record

_NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000000a1")


def _stored(event_type: str, version: int, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=version,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        version=version,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        occurred_at=_NOW,
        recorded_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
    )


def _pin(version: int, marker: str) -> StoredEvent:
    return _stored(
        "ResolvedStepsRecorded",
        version,
        {
            "procedure_id": str(_PROCEDURE_ID),
            "resolved_steps": [{"kind": "action", "name": marker}],
            "step_count": 1,
        },
    )


@pytest.mark.unit
def test_find_resolved_steps_record_on_empty_stream_returns_none() -> None:
    assert find_resolved_steps_record([]) is None


@pytest.mark.unit
def test_find_resolved_steps_record_without_a_pin_returns_none() -> None:
    events = [_stored("ProcedureRegistered", 1, {}), _stored("ProcedureStarted", 2, {})]
    assert find_resolved_steps_record(events) is None


@pytest.mark.unit
def test_find_resolved_steps_record_with_one_pin_returns_it() -> None:
    pin = _pin(2, "only")
    events = [
        _stored("ProcedureRegistered", 1, {}),
        pin,
        _stored("ProcedureStarted", 3, {}),
    ]
    assert find_resolved_steps_record(events) is pin


@pytest.mark.unit
def test_find_resolved_steps_record_with_two_matches_returns_first_match() -> None:
    """Observed behaviour, and the reason the docstrings needed correcting.

    The finder head-scans, so a stream carrying more than one pin yields the
    first. That is scan order, not a judgement about which pin governed the
    conduct, and the finder cannot tell the difference.

    This assertion is expected to INVERT when the read side is corrected to
    take the last pin preceding `ProcedureStarted`. A green result here is a
    record of what the code does, not a specification of what it should.
    """
    first, second = _pin(2, "first"), _pin(3, "second")
    found = find_resolved_steps_record([first, second])

    assert found is not None
    assert found is first
    assert found.payload["resolved_steps"] == [{"kind": "action", "name": "first"}]


@pytest.mark.unit
def test_find_resolved_steps_record_stops_at_the_first_match() -> None:
    """The docstring promises an early exit, so the laziness is contract.

    The parameter is an `Iterable`, so a caller may hand over a generator
    whose later elements are expensive or unavailable. Mirrors the sibling
    guard in `test_recipe_replay.py`.
    """

    def _events() -> Iterator[StoredEvent]:
        yield _stored("ProcedureRegistered", 1, {})
        yield _pin(2, "only")
        raise AssertionError("scanned past the first match")

    found = find_resolved_steps_record(_events())

    assert found is not None
    assert found.event_type == "ResolvedStepsRecorded"
