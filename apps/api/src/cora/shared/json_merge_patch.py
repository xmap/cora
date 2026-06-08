"""RFC 7396 JSON Merge Patch implementation.

Hoisted (originally lived in
`cora.equipment.aggregates.asset.settings_validation`) once
the third call site landed. Use sites:

  - `update_asset_settings` (Equipment) — Asset.settings PATCH
  - `update_plan_default_parameters` (Recipe) — Plan defaults PATCH
  - `start_run` (Run) — effective_parameters = merge(plan.default_parameters,
    command.override_parameters)

Three sites across three BCs is the rule-of-three threshold (matches
the `json_schema_subset` hoist precedent, which had the same shape:
shared structural utility used by multiple BCs).

## Why RFC 7396 over RFC 6902

CORA's parameter / settings dicts are small flat-ish objects of
primitive values; null naturally maps to "delete". RFC 6902 (JSON
Patch, operation-array shape) is more expressive but unnecessary
for this use case. Industry confirms (research, May 2026):
no serious modern alternative has displaced either RFC since their
2014 publication.

## RFC 7396 limitations CORA accepts

  - Cannot represent "set key to null" — null is the delete sentinel.
    CORA's domain values are never null (use absence or a typed
    sentinel like `Optional[X] = None` at the dataclass layer).
  - Cannot patch array elements at a specific index. CORA's parameter
    and settings dicts use flat scalar keys, not nested arrays — if
    a future use case needs array-element ops, switch the affected
    slice to RFC 6902 patches; this module's RFC 7396 implementation
    stays as-is.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import copy
from collections.abc import Mapping
from typing import Any


def merge_patch(current: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """Apply RFC 7396 JSON Merge Patch semantics.

    Returns a NEW deeply-copied dict (does not alias `current` at any
    nesting depth):
      - keys in `patch` with non-null values: set / replace
      - keys in `patch` with null: deleted from result
      - keys absent from `patch`: preserved from `current`

    Recursive on nested dicts: `merge_patch({"a": {"b": 1}}, {"a":
    {"c": 2}}) == {"a": {"b": 1, "c": 2}}`. RFC 7396 says nested
    null also deletes (`merge_patch({"a": {"b": 1}}, {"a": {"b":
    null}}) == {"a": {}}`).

    The result is `copy.deepcopy`'d so caller mutations of the
    returned dict do not propagate into `current` or into the event
    payload that this dict becomes. CORA's parameter/settings dicts
    are typically small (5-30 keys), so deepcopy cost is negligible
    compared to the safety guarantee.

    Note: cannot represent "set key to null" — null is overloaded as
    the delete sentinel. CORA values are never null in practice.
    """
    result: dict[str, Any] = copy.deepcopy(dict(current))
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            # Recursive merge into existing nested dict
            result[key] = merge_patch(result[key], value)
        else:
            # Set / replace (including dict-into-non-dict and scalars).
            # Deep-copy the patch value so caller mutations of the
            # patch don't propagate into the result either.
            result[key] = copy.deepcopy(value)
    return result


__all__ = ["merge_patch"]
