"""The generic recursive leaf rule.

Shared by tier-1's `by-value` polymorphic fields (a slot that can hold a
scalar or a value object -- `_dispositions.py`'s `by-value` disposition)
and tier-2's four recursing jsonb columns (`activities.payload`,
`diagnostics.payload`, `outcomes.point`, `outcomes.measurements`). Per
`project_record_export_v3.md` F5: numeric and boolean leaves KEEP,
UUID-shaped string leaves TOKEN, every other string leaf DROPS unless
its `(column, json-pointer)` is on a caller-supplied cleared list.
Object KEYS are always published -- in practice they are field names
and they carry the structure -- only VALUES are ever redacted.

This walker does not know, or need to know, what produced the value it
is walking (which `step_kind`, which Recipe step type, ...). That is
deliberate: a nested shape nobody enumerated a clearance for simply
drops by the same default every other unlisted field drops by, rather
than needing a special case per producer.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# Walks `Any`-typed, already-rendered JSON values; suppressed the same
# way cora.shared.content_hash._canonicalize is, for the same reason.

import re
from typing import Any

from cora.infrastructure.record_export._tokens import TokenMap

OMITTED = object()
"""Sentinel: the caller must omit this key (dict) or this element (list)
entirely, not store `None` in its place."""

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_uuid_shaped(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _join_pointer(pointer: str, segment: str) -> str:
    return segment if not pointer else f"{pointer}/{segment}"


def apply_leaf_rule(
    value: Any,
    *,
    token_map: TokenMap,
    cleared_pointers: frozenset[str] = frozenset(),
    pointer: str = "",
    fired_pointers: set[str] | None = None,
) -> Any:
    """Recursively redact `value`.

    Returns a redacted `dict`/`list` (same shape, dropped keys/elements
    omitted) for a container, a redacted scalar for a leaf, or `OMITTED`
    if the top-level value itself is a leaf that must be omitted by the
    caller (dict/list values are never themselves `OMITTED` -- an empty
    dict/list is a valid redacted result and is returned as such).

    `fired_pointers`, when supplied, collects every `pointer` whose
    value was actually kept via `cleared_pointers` (not via the
    unconditional number/bool/None/UUID branches) -- the record needed
    to check a cleared list ever matched anything, per F5's
    unfired-clearance rejection.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, sub_value in value.items():
            child_pointer = _join_pointer(pointer, str(key))
            redacted = apply_leaf_rule(
                sub_value,
                token_map=token_map,
                cleared_pointers=cleared_pointers,
                pointer=child_pointer,
                fired_pointers=fired_pointers,
            )
            if redacted is not OMITTED:
                result[key] = redacted
        return result

    if isinstance(value, (list, tuple)):
        child_pointer = _join_pointer(pointer, "*")
        out: list[Any] = []
        for item in value:
            redacted = apply_leaf_rule(
                item,
                token_map=token_map,
                cleared_pointers=cleared_pointers,
                pointer=child_pointer,
                fired_pointers=fired_pointers,
            )
            if redacted is not OMITTED:
                out.append(redacted)
        return out

    # Leaf values.
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if is_uuid_shaped(value):
            return token_map.token_uuid(value)
        if pointer in cleared_pointers:
            if fired_pointers is not None:
                fired_pointers.add(pointer)
            return value
        return OMITTED

    # An already-rendered export body (per step 2's F6) never contains
    # anything else; fail closed rather than guess at a new type's intent.
    return OMITTED


__all__ = ["OMITTED", "apply_leaf_rule", "is_uuid_shaped"]
