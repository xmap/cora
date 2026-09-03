"""Helpers for getting at a stored event's payload: find it, then decode it.

Two concerns, joined because every caller of the first immediately wants
the second: `find_first_event` / `find_last_event` locate the ONE event
carrying the payload a reader needs, and `deserialize_or_raise` /
`deserialize_vo_or_raise` wrap the decoding of that payload.

## Locating an event in a loaded stream

`find_first_event` and `find_last_event` differ only in direction, and
the direction is a real decision each caller must make rather than a
style choice: a genesis record is the FIRST of its type and any later
one is not it, while a record a retry can re-emit is the LAST, and
reading that one from the head returns the abandoned attempt. Neither
function has an opinion about which is right; the named domain finders
that wrap them carry that knowledge in their own docstrings, which is
where a reader looking at a call site will be.

## Wrapping a decode

Two free functions sharing the same try / wrap / re-raise body but
keyed on different identity dimensions:

  - `deserialize_or_raise(event_type, ...)` -- wraps each `case "X":`
    arm in an aggregate's `from_stored` dispatch; first argument names
    the EVENT TYPE.
  - `deserialize_vo_or_raise(vo_type, ...)` -- wraps each nested VO
    decoder (e.g. `deserialize_target`, `deserialize_binding`,
    `deserialize_classification`) that sits ABOVE `from_stored` as a
    sub-helper; first argument names the VO TYPE.

The two helpers stay separate because the first-argument identity
differs (event-type vs vo-type) and because the VO helper needs a
`raise_as` knob (calibration's `deserialize_source` raises typed
`InvalidCalibrationSourceError(ValueError)` rather than bare
`ValueError`). Combining them under a `no_payload_echo` flag would
conflate two domains and risk silent message-shape drift.

Why these helpers exist
-----------------------
Hoisted after the 28th `from_stored` shipped 162 inline
`except (KeyError, TypeError, AttributeError)` wrap sites that
re-raise as `ValueError("Malformed {event_type} payload ...")`.

Why a free function (not a decorator or base class)
---------------------------------------------------
Each per-aggregate `from_stored` is a `match stored.event_type:`
dispatch where each arm builds an event dataclass. The shared
shape across all 162 sites is the **try / wrap / re-raise** body,
not the dispatch or the builder expression itself. A free function
lets each `case "X":` arm stay a one-line call:

    case "ActorRegisteredV2":
        return deserialize_or_raise(
            "ActorRegisteredV2",
            lambda: ActorRegistered(
                actor_id=UUID(payload["actor_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                kind=ActorKind(payload["kind"]),
            ),
            extra=(ValueError,),
        )

A decorator on the case arm is impossible (Python match-case arms
cannot be decorated). A base class would force every aggregate's
event union through an inheritance chain for zero structural
benefit. The free-function form keeps each arm legible inside the
existing `match` body.

Why `extra` is a keyword tuple
------------------------------
Six call sites need to additionally catch `ValueError` raised by
inline `Enum(payload[k])` calls (ActorKind, SurfaceKind, Direction,
AbiTier). The default empty tuple matches the 156-site majority;
the 6 sites pass `extra=(ValueError,)`.

Why the payload is NOT echoed in the message
--------------------------------------------
The legacy per-site message was
`f"Malformed {event_type} payload {payload!r}: {exc}"`. Echoing the
raw payload into a `ValueError` string leaks fields into
log aggregators (Sentry, Datadog) that may correlate against
the PII-vault `actor_profile` rows. The architecture fitness at
`tests/architecture/test_from_stored_wraps_payload.py` asserts only
the `"Malformed {event_type} payload"` substring; no unit test
asserts on the echo. Dropping the echo is fitness-safe and
log-hygienic.

Why `message_suffix` is keyword-only
------------------------------------
Exactly one call site (Actor's `ActorRegistered` V1 arm) carries a
` (V1)` suffix in the legacy message to distinguish it from the
modern `ActorRegisteredV2` arm. The suffix is placed AFTER the
`payload` token so the fitness substring (`Malformed
ActorRegistered payload`) survives unchanged.

Why `raise_as` lives only on the VO helper
------------------------------------------
The event-type wrap always re-raises as bare `ValueError` (callers
in `from_stored` arms then opt into wider catches via `extra`).
Nested VO helpers occasionally need a typed `ValueError` subclass:
calibration's `deserialize_source` raises
`InvalidCalibrationSourceError(ValueError)` so the outer
`from_stored` arm's `extra=(ValueError,)` absorbs it at the
event-type wrap layer.
"""

from collections.abc import Callable, Iterable, Sequence

from cora.infrastructure.ports.event_store import StoredEvent


def deserialize_or_raise[EventT](
    event_type: str,
    builder: Callable[[], EventT],
    *,
    extra: tuple[type[BaseException], ...] = (),
    message_suffix: str = "",
) -> EventT:
    """Run `builder` and re-raise stored-event decoding failures as `ValueError`.

    Catches `KeyError`, `TypeError`, `AttributeError`, plus any
    classes in `extra`; re-raises a `ValueError` carrying the
    canonical `"Malformed {event_type} payload{message_suffix}: {exc}"`
    text. The original exception is chained via `__cause__`.

    The raw payload is intentionally NOT included in the message;
    see module docstring for the PII-hygiene rationale.
    """
    try:
        return builder()
    except (KeyError, TypeError, AttributeError, *extra) as exc:
        msg = f"Malformed {event_type} payload{message_suffix}: {exc}"
        raise ValueError(msg) from exc


def deserialize_vo_or_raise[VoT](
    vo_type: str,
    builder: Callable[[], VoT],
    *,
    extra: tuple[type[BaseException], ...] = (),
    raise_as: type[ValueError] = ValueError,
) -> VoT:
    """Run `builder` and re-raise nested-VO decoding failures as `raise_as`.

    Catches `KeyError`, `TypeError`, `AttributeError`, plus any
    classes in `extra`; re-raises `raise_as` (default `ValueError`)
    carrying the canonical `"Malformed {vo_type} payload: {exc}"`
    text. The original exception is chained via `__cause__`.

    The raw payload is intentionally NOT included in the message;
    see module docstring for the PII-hygiene rationale (same as
    `deserialize_or_raise`).

    The `raise_as` knob covers calibration's `deserialize_source`
    whose VO helper raises typed
    `InvalidCalibrationSourceError(ValueError)` so the outer
    `from_stored` arm's `extra=(ValueError,)` absorbs it at the
    event-type wrap layer.
    """
    try:
        return builder()
    except (KeyError, TypeError, AttributeError, *extra) as exc:
        msg = f"Malformed {vo_type} payload: {exc}"
        raise raise_as(msg) from exc


def find_first_event(
    stored_events: Iterable[StoredEvent],
    event_type: str,
) -> StoredEvent | None:
    """The FIRST event of `event_type` in a loaded stream, or None.

    Scans from the head and early-exits on the first hit. Correct where
    the wanted record is a genesis one, which by definition cannot be
    superseded by a later event of the same type.
    """
    for event in stored_events:
        if event.event_type == event_type:
            return event
    return None


def find_last_event(
    stored_events: Sequence[StoredEvent],
    event_type: str,
) -> StoredEvent | None:
    """The LAST event of `event_type` in a loaded stream, or None.

    Scans from the tail. Correct where a later event of the same type
    SUPERSEDES an earlier one, which is the case for any record a failed
    attempt can leave behind and a retry can re-emit with different
    content. Takes a `Sequence` rather than an `Iterable` because
    reversing needs a known end.
    """
    for event in reversed(stored_events):
        if event.event_type == event_type:
            return event
    return None


__all__ = [
    "deserialize_or_raise",
    "deserialize_vo_or_raise",
    "find_first_event",
    "find_last_event",
]
