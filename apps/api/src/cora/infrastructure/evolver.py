"""Shared helpers for aggregate evolvers (event replay).

Hoisted once the 11th identical `_require_state` copy landed
(Subject / Run / Asset / Family / Decision / Dataset /
Method / Practice / Plan / Conduit / Supply). All 11 had the same
five-line body byte-for-byte; only the aggregate type parameter
differed.

## What this module owns

  - `require_state[T]` — guard for transition-event match arms:
    the prior state must be non-`None` (an empty stream cannot
    receive a transition event; that would mean the event log
    is corrupt or the events are being replayed in the wrong
    order). Returns the prior state on success; raises
    `ValueError` otherwise.

The genesis-event arm of each evolver still expects `state is
None` and constructs the initial aggregate inline; this helper
is for non-genesis arms only.

## Why a free function (not a base class or mixin)

Same rationale as `validate_bounded_text` (see
`cora.shared.bounded_text`): a per-aggregate distinct
type at the call site keeps `isinstance` checks aggregate-
specific and lets pyright narrow correctly through the match
arms. A free generic function preserves that while retiring the
copy-paste body.
"""


def require_state[T](state: T | None, event_type: str) -> T:
    """Return `state` or raise `ValueError` if `state is None`.

    Used in evolver match arms for transition events (everything
    except the genesis event of the stream). An empty stream
    receiving a transition event is corruption; this helper makes
    that assertion uniform across aggregates.
    """
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


__all__ = ["require_state"]
