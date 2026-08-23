"""binary_code: resolve a two-state substrate reading to 0 / 1, or neither.

Originated in `cora.api._enclosure_permit_observer._binary_code`
(2026-08-09, fixing a production incident where `int('ON')` raised and
a correctly secured hutch read as `Unknown` forever). Copied verbatim
into `cora.operation.adapters.control_port_beam_availability_lookup`
(2026-08-18, the identical defect on the beam-permit PVs) and into
`cora.api._capture_observer` as the module-public `binary_code`
(`capture_watch_preflight` needed to call it directly). That third
occurrence's docstring already said a fourth should hoist rather than
copy again; the BLEPS supply observer is that fourth, so this module
is the hoist.

## The ordinal is the portable half, and it comes first

The three incidents above share one shape: a facility spelled its enum
labels differently and CORA read nothing. That kept being fixed by
widening the label set, which cannot converge. `ZNAM` / `ONAM` (EPICS),
`enum_labels` (Tango) and `value.choices` (PVA) are free text one
engineer chose at one facility, constrained by nothing, so no label set
is ever complete. 2-BM's BLEPS proved it in the field: its flags read
`NO_FAULT` / `TRIP`, and its comms flag reads the EMPTY STRING for
healthy, neither of which any conventional set would contain.

The index behind those labels is not free text. It is 0 / 1 on every
substrate CORA speaks, and every adapter already holds it at the moment
it picks a label (see `Measurement.ordinal`). So `ordinal` decides when
the adapter supplied one, and the label vocabulary below is the
FALLBACK, kept for readings that carry no ordinal: a genuine string
record, an adapter that resolved no index, or a test constructing a
reading by hand.

## What preferring the index gives up

Deliberate, accepted 2026-08-23, and worth stating plainly because the
loss is invisible from the passing tests. An unconventional label used
to resolve to `None`, so a consumer pointed at the WRONG record often
failed closed by accident: a beam gate misconfigured onto a
`Closed` / `Open` shutter readback got `binary_code("Closed") -> None`
and blocked. That same reading now carries index 0 and is believed, and
on the polarity-inverted shutters 0 means OPEN.

The old behavior was a coincidence rather than a check. It fired only
when the wrong record happened to carry unconventional labels, missed
every wrong record whose labels were conventional, and REJECTED correct
records whose labels were not, which is the defect this module exists
to close. Trading an inconsistent filter for a consistent decode is the
right trade, but it is a trade and not a free win.

What remains catches strictly less than that: the out-of-range check
below fires only if the wrong record happens to be resting outside
0 / 1 when it is read, so the same mis-pointed `mbbi` sitting in state 0
is trusted with full confidence. Whether a deployment is pointed at the
right address is not a question this module can answer. A real check
needs information it does not have, for instance an adapter publishing
the record's state COUNT so a two-state question could refuse a
sixteen-state record. That is deliberately NOT built here: it would
couple the ordinal to label resolution, and the ordinal's independence
from the label cache is what makes it correct on a cold first read.

`ordinal` is a REQUIRED keyword rather than a defaulted one on purpose.
A caller that forgets it would silently fall back to label matching and
re-open exactly the defect this module exists to close, and that failure
is invisible until a facility with unconventional labels deploys.
Required means pyright counts the CONSUMER sites instead of a reviewer.

That guarantee covers one side only. `Measurement.ordinal` itself
defaults to `None`, so any PRODUCER (a new adapter, a serializer that
rebuilds a reading, a test double) can omit it in silence and every
consumer of that reading quietly reverts to label matching. Nothing
type-checks that away; `tests/unit/operation/test_enum_ordinal_mapping.py`
is the drift catcher that does, and a new adapter belongs in it.

`cora.shared` has no dependencies of its own (tach), so this module
cannot import `Measurement` and takes the two fields it needs as plain
arguments. Any BC or composition-root adapter may use it without adding
a cross-BC edge.
"""

from __future__ import annotations

# Conventional EPICS binary state labels, the FALLBACK path only. A
# DBR_ENUM reading (a `bi` / `mbbi` record) reaches a ControlPort adapter
# as its resolved FORMAT_CTRL label; `CaprotoControlPort`, by contrast,
# leaves the raw integer unresolved, which the `int(value)` arm covers.
# Neither is consulted when the caller supplies an ordinal.
_ONE_LABELS = frozenset({"1", "ON", "TRUE", "YES"})
_ZERO_LABELS = frozenset({"0", "OFF", "FALSE", "NO"})


def binary_code(value: object, *, ordinal: int | None) -> int | None:
    """Resolve a two-state reading to 1 / 0, or `None` when it is neither.

    Pass `Measurement.ordinal` and `Measurement.value` from the same
    reading. The ordinal wins whenever it is present, because it is the
    substrate's own answer rather than the facility's wording of it;
    `value` is consulted only when `ordinal` is `None`.

    Polarity is NOT decided here: this only turns a reading into 0 / 1.
    The caller applies whatever the signal's own polarity means
    (open/closed, permitted/not, tripped/clear, ...).

    Unrecognized resolves to `None`, never a guess: mapping a label this
    function does not recognize to 0 or 1 would be inventing a fact about
    a record nobody here has read. A reading outside {0, 1} (a stray 2, or
    an ordinal pointing at the third state of an `mbbi`) also resolves to
    `None`, not to its raw value: the caller asked a two-state question,
    so an out-of-range answer is not a third state to interpret, it is a
    signal that the caller is pointed at the wrong record, and that should
    fail closed like any other unbelievable reading.
    """
    if ordinal is not None:
        return ordinal if ordinal in (0, 1) else None
    if isinstance(value, str):
        token = value.strip().upper()
        if token in _ONE_LABELS:
            return 1
        if token in _ZERO_LABELS:
            return 0
        return None
    if isinstance(value, float) and not value.is_integer():
        # `int(0.4)` truncates to 0, and 0 is a CONFIRMED state to every
        # caller: on the polarity-inverted beam shutters it means "open".
        # A fractional reading on a two-state signal says the caller is
        # not looking at a flag, so it fails closed rather than rounding
        # toward whichever answer the truncation happens to give.
        # `control_port_beam_availability_lookup` has guarded this at its
        # own call site since the beam gate shipped; the guard belongs
        # here now that four other consumers share this decoder, and it
        # stays there as belt-and-braces.
        return None
    try:
        code = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return code if code in (0, 1) else None


__all__ = ["binary_code"]
