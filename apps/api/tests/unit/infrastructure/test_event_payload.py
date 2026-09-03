"""Unit tests for `cora.infrastructure.event_payload` helpers.

Coverage for `deserialize_or_raise` (event-type wrap):
  - Successful build returns the constructed event unchanged
  - KeyError / TypeError / AttributeError each become `ValueError`
    tagged `Malformed {event_type} payload`
  - Raw payload is NEVER echoed into the `ValueError` message
    (PII-vault correlation hygiene; see module docstring)
  - Original exception preserved via `__cause__`
  - `extra` widens the catch tuple (covers the 6 quadruple sites
    that wrap inline `Enum(payload[k])` calls)
  - `message_suffix` is placed after `payload` so the architecture
    fitness substring (`Malformed {n} payload`) survives unchanged
  - Exceptions outside the catch tuple propagate unchanged

Coverage for `deserialize_vo_or_raise` (nested-VO wrap):
  - Successful build returns the constructed VO unchanged
  - KeyError / TypeError / AttributeError each become `ValueError`
    tagged `Malformed {vo_type} payload`
  - Raw payload is NEVER echoed into the `ValueError` message
  - Original exception preserved via `__cause__`
  - `raise_as` re-raises a typed `ValueError` subclass (covers
    calibration's `InvalidCalibrationSourceError`)
  - `extra` widens the catch tuple
  - Exceptions outside the catch tuple propagate unchanged

Coverage for `find_first_event` / `find_last_event` (stream locate):
  - each returns None on an empty stream and on a stream with no match
  - each ignores events of other types, including ones surrounding the match
  - with SEVERAL matches the two return DIFFERENT events, which is the only
    reason both exist
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_payload import (
    deserialize_or_raise,
    deserialize_vo_or_raise,
    find_first_event,
    find_last_event,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
_STREAM_ID = UUID("01900000-0000-7000-8000-0000000000f1")


@dataclass(frozen=True)
class _FooEvent:
    actor_id: str
    count: int


@pytest.mark.unit
def test_deserialize_or_raise_returns_built_event_on_success() -> None:
    result = deserialize_or_raise(
        "FooEvent",
        lambda: _FooEvent(actor_id="a-1", count=2),
    )
    assert result == _FooEvent(actor_id="a-1", count=2)


@pytest.mark.unit
def test_deserialize_or_raise_wraps_key_error_as_value_error() -> None:
    payload: dict[str, str] = {}
    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise("FooEvent", lambda: _FooEvent(actor_id=payload["missing"], count=0))


@pytest.mark.unit
def test_deserialize_or_raise_wraps_type_error_as_value_error() -> None:
    payload: dict[str, object] = {"actor_id": ["not", "a", "string"]}
    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise(
            "FooEvent",
            lambda: _FooEvent(actor_id=payload["actor_id"] + 1, count=0),  # type: ignore[operator]
        )


@pytest.mark.unit
def test_deserialize_or_raise_wraps_attribute_error_as_value_error() -> None:
    def builder() -> _FooEvent:
        bogus: object = object()
        return _FooEvent(actor_id=bogus.actor_id, count=1)  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise("FooEvent", builder)


@pytest.mark.unit
def test_deserialize_or_raise_preserves_original_via_cause() -> None:
    original = KeyError("actor_id")
    with pytest.raises(ValueError) as exc_info:
        deserialize_or_raise("FooEvent", lambda: (_ for _ in ()).throw(original))
    assert exc_info.value.__cause__ is original


@pytest.mark.unit
def test_deserialize_or_raise_does_not_echo_payload_in_message() -> None:
    """Raw payload contents must NOT leak into the ValueError text.
    The fitness test asserts only the `Malformed {n} payload` substring;
    payload values may carry PII-vault correlatable ids that should
    not surface in log aggregators."""
    sensitive = "actor-id-7b3f1a8e-secret"
    payload = {"actor_id": sensitive}
    with pytest.raises(ValueError) as exc_info:
        deserialize_or_raise("FooEvent", lambda: _FooEvent(actor_id=payload["missing"], count=0))
    assert sensitive not in str(exc_info.value)


@pytest.mark.unit
def test_deserialize_or_raise_extra_widens_catch_tuple_for_value_error() -> None:
    """The 6 quadruple sites pass `extra=(ValueError,)` to absorb
    inline `Enum(payload[k])` failures."""
    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise(
            "FooEvent",
            lambda: (_ for _ in ()).throw(ValueError("bad enum value")),
            extra=(ValueError,),
        )


@pytest.mark.unit
def test_deserialize_or_raise_without_extra_lets_value_error_propagate() -> None:
    """Default empty `extra` must NOT swallow domain ValueErrors raised
    outside the (K/T/A) triple. Mirrors `deserialize_source` in
    `calibration/aggregates/calibration/events.py` which raises a
    typed `InvalidCalibrationSourceError` (a ValueError subclass) that
    must reach callers untransformed."""
    domain_error = ValueError("typed domain failure")
    with pytest.raises(ValueError) as exc_info:
        deserialize_or_raise(
            "FooEvent",
            lambda: (_ for _ in ()).throw(domain_error),
        )
    assert exc_info.value is domain_error


@pytest.mark.unit
def test_deserialize_or_raise_message_suffix_placed_after_payload_token() -> None:
    """The fitness regex matches `Malformed {n} payload` as a literal
    substring. The suffix MUST sit after `payload` so the Actor V1 arm
    can disambiguate without breaking the substring."""
    with pytest.raises(ValueError, match=r"Malformed ActorRegistered payload \(V1\)"):
        deserialize_or_raise(
            "ActorRegistered",
            lambda: (_ for _ in ()).throw(KeyError("actor_id")),
            message_suffix=" (V1)",
        )


@pytest.mark.unit
def test_deserialize_or_raise_propagates_unrelated_exception_types() -> None:
    """Exceptions outside the catch tuple (and outside `extra`) reach
    the caller unchanged. Mirrors `InvalidCalibrationSourceError` raised
    by `deserialize_source` which intentionally bypasses the generic
    wrap."""

    class _DomainError(Exception):
        pass

    with pytest.raises(_DomainError):
        deserialize_or_raise(
            "FooEvent",
            lambda: (_ for _ in ()).throw(_DomainError("domain-specific")),
        )


@pytest.mark.unit
def test_deserialize_or_raise_carries_event_type_into_message() -> None:
    with pytest.raises(ValueError, match="Malformed SomeOtherEvent payload"):
        deserialize_or_raise(
            "SomeOtherEvent",
            lambda: (_ for _ in ()).throw(KeyError("x")),
        )


@dataclass(frozen=True)
class _BarVo:
    name: str
    count: int


class _TypedVoError(ValueError):
    """Mirrors calibration's `InvalidCalibrationSourceError`."""


@pytest.mark.unit
def test_deserialize_vo_or_raise_returns_built_vo_on_success() -> None:
    result = deserialize_vo_or_raise(
        "BarVo",
        lambda: _BarVo(name="alpha", count=3),
    )
    assert result == _BarVo(name="alpha", count=3)


@pytest.mark.unit
def test_deserialize_vo_or_raise_wraps_key_error_as_value_error() -> None:
    payload: dict[str, str] = {}
    with pytest.raises(ValueError, match="Malformed ModelRef payload"):
        deserialize_vo_or_raise(
            "ModelRef",
            lambda: _BarVo(name=payload["missing"], count=0),
        )


@pytest.mark.unit
def test_deserialize_vo_or_raise_wraps_type_error_as_value_error() -> None:
    payload: dict[str, object] = {"name": ["not", "a", "string"]}
    with pytest.raises(ValueError, match="Malformed ModelRef payload"):
        deserialize_vo_or_raise(
            "ModelRef",
            lambda: _BarVo(name=payload["name"] + 1, count=0),  # type: ignore[operator]
        )


@pytest.mark.unit
def test_deserialize_vo_or_raise_wraps_attribute_error_as_value_error() -> None:
    def builder() -> _BarVo:
        bogus: object = object()
        return _BarVo(name=bogus.missing, count=1)  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="Malformed ModelRef payload"):
        deserialize_vo_or_raise("ModelRef", builder)


@pytest.mark.unit
def test_deserialize_vo_or_raise_does_not_echo_payload_in_message() -> None:
    """Raw payload contents must NOT leak into the ValueError text.
    Same PII-vault correlation hygiene as `deserialize_or_raise`."""
    sensitive = "actor-id-7b3f1a8e-secret"
    payload = {"name": sensitive}
    with pytest.raises(ValueError) as exc_info:
        deserialize_vo_or_raise(
            "ModelRef",
            lambda: _BarVo(name=payload["missing"], count=0),
        )
    assert sensitive not in str(exc_info.value)


@pytest.mark.unit
def test_deserialize_vo_or_raise_preserves_original_via_cause() -> None:
    original = KeyError("provider")
    with pytest.raises(ValueError) as exc_info:
        deserialize_vo_or_raise(
            "ModelRef",
            lambda: (_ for _ in ()).throw(original),
        )
    assert exc_info.value.__cause__ is original


@pytest.mark.unit
def test_deserialize_vo_or_raise_raise_as_uses_subclass() -> None:
    """`raise_as` re-raises the typed `ValueError` subclass instead
    of bare `ValueError`. Mirrors calibration's `deserialize_source`
    which raises `InvalidCalibrationSourceError(ValueError)`."""
    with pytest.raises(_TypedVoError) as exc_info:
        deserialize_vo_or_raise(
            "CalibrationSource",
            lambda: (_ for _ in ()).throw(TypeError("bad shape")),
            raise_as=_TypedVoError,
        )
    assert isinstance(exc_info.value, _TypedVoError)
    assert str(exc_info.value).startswith("Malformed CalibrationSource payload")


@pytest.mark.unit
def test_deserialize_vo_or_raise_extra_widens_catch_tuple() -> None:
    with pytest.raises(ValueError, match="Malformed BarVo payload"):
        deserialize_vo_or_raise(
            "BarVo",
            lambda: (_ for _ in ()).throw(ValueError("bad enum value")),
            extra=(ValueError,),
        )


@pytest.mark.unit
def test_deserialize_vo_or_raise_propagates_unrelated_exception_types() -> None:
    """Exceptions outside the catch tuple (and outside `extra`) reach
    the caller unchanged."""

    class _DomainError(Exception):
        pass

    with pytest.raises(_DomainError):
        deserialize_vo_or_raise(
            "BarVo",
            lambda: (_ for _ in ()).throw(_DomainError("domain-specific")),
        )


# --- find_first_event / find_last_event (locate one event in a loaded stream) ---


def _stored(event_type: str, version: int, marker: str) -> StoredEvent:
    return StoredEvent(
        position=version,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=_STREAM_ID,
        version=version,
        event_type=event_type,
        schema_version=1,
        payload={"marker": marker},
        occurred_at=_NOW,
        recorded_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
    )


def _stream() -> list[StoredEvent]:
    """A pin surrounded by other types, and re-emitted by a later attempt."""
    return [
        _stored("Registered", 1, "genesis"),
        _stored("Pinned", 2, "first"),
        _stored("Other", 3, "noise"),
        _stored("Pinned", 4, "second"),
        _stored("Started", 5, "started"),
    ]


@pytest.mark.unit
@pytest.mark.parametrize("find", [find_first_event, find_last_event])
def test_find_event_on_an_empty_stream_returns_none(
    find: Callable[[list[StoredEvent], str], StoredEvent | None],
) -> None:
    assert find([], "Pinned") is None


@pytest.mark.unit
@pytest.mark.parametrize("find", [find_first_event, find_last_event])
def test_find_event_with_no_match_returns_none(
    find: Callable[[list[StoredEvent], str], StoredEvent | None],
) -> None:
    assert find(_stream(), "NeverWritten") is None


@pytest.mark.unit
def test_find_first_event_returns_the_earliest_match_not_the_earliest_event() -> None:
    found = find_first_event(_stream(), "Pinned")

    assert found is not None
    assert found.payload["marker"] == "first"


@pytest.mark.unit
def test_find_last_event_returns_the_latest_match_not_the_latest_event() -> None:
    found = find_last_event(_stream(), "Pinned")

    assert found is not None
    assert found.payload["marker"] == "second"


@pytest.mark.unit
def test_find_first_and_find_last_disagree_when_a_type_repeats() -> None:
    """The whole reason both exist.

    A single finder would force every caller onto one direction, and the two
    directions answer different questions: which record STARTED this stream,
    versus which record is now in force. Asserting each in isolation would
    stay green if both were wired to the same scan.
    """
    stream = _stream()

    first = find_first_event(stream, "Pinned")
    last = find_last_event(stream, "Pinned")

    assert first is not None
    assert last is not None
    assert first is not last
    assert (first.payload["marker"], last.payload["marker"]) == ("first", "second")


@pytest.mark.unit
@pytest.mark.parametrize("find", [find_first_event, find_last_event])
def test_find_event_with_exactly_one_match_returns_it_from_either_direction(
    find: Callable[[list[StoredEvent], str], StoredEvent | None],
) -> None:
    found = find(_stream(), "Started")

    assert found is not None
    assert found.payload["marker"] == "started"
