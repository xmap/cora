"""binary_code: resolve an EPICS binary reading to 0 / 1, or neither.

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

`cora.shared` has no dependencies of its own (tach), so any BC or
composition-root adapter may use this without adding a cross-BC edge.
"""

from __future__ import annotations

# Conventional EPICS binary state labels. A DBR_ENUM reading (a `bi` /
# `mbbi` record) reaches a ControlPort adapter as its resolved FORMAT_CTRL
# label, never as its raw index, so the label is the only thing left to
# compare against once a caller wants a plain 0 / 1. `CaprotoControlPort`,
# by contrast, leaves the raw integer unresolved, which the `int(value)`
# fallback below covers.
_ONE_LABELS = frozenset({"1", "ON", "TRUE", "YES"})
_ZERO_LABELS = frozenset({"0", "OFF", "FALSE", "NO"})


def binary_code(value: object) -> int | None:
    """Resolve a binary-signal reading to 1 / 0, or `None` when it is neither.

    Polarity is NOT decided here: this only turns a raw reading (an int,
    an integral float, or an EPICS enum label) into 0 / 1. The caller
    applies whatever the PV's own polarity means (open/closed,
    permitted/not, tripped/clear, ...).

    Unrecognized resolves to `None`, never a guess: mapping a label this
    function does not recognize to 0 or 1 would be inventing a fact about
    a record type nobody here has read. A numeric reading outside {0, 1}
    (e.g. a stray 2) also resolves to `None`, not to its raw value: these
    are two-state records, so an out-of-range reading is not a third
    state to interpret, it is a signal that something upstream is wrong,
    and that should fail closed like any other unbelievable reading
    rather than be read with confidence.
    """
    if isinstance(value, str):
        token = value.strip().upper()
        if token in _ONE_LABELS:
            return 1
        if token in _ZERO_LABELS:
            return 0
        return None
    try:
        code = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return code if code in (0, 1) else None


__all__ = ["binary_code"]
