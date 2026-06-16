"""Discrete index-to-position table: operating_point + value schemas.

The position a selector takes for each of a finite set of named slots: a
filter foil carousel, a mirror coating-stripe selector, a lens turret.
The operator picks a slot by index; the table maps that slot to a saved
motor position. This is the discrete sibling of `energy_position_curve`:
where the curve evaluates a continuous relationship across energy, this
table snaps to one of N saved positions (the consuming `LookupTable`
rule uses `interpolation_kind = Nearest`).

The independent variable is the slot INDEX, taken from the array order of
`points` (slot 0 is the first entry, slot 1 the second, ...). Each entry
also carries a human `name` (for example `"600 um Al"`, `"None"`) that is
documentary: it keeps event logs and audit trails intelligible, but the
kernel keys on the numeric index because the pseudoaxis command path is
numeric (the operator commands an integer index, and `Nearest` snaps to
the closest tabulated slot). Energy is NOT involved: a foil carousel is
the same regardless of beam energy, so there is no energy key here (the
attenuation a foil produces DOES depend on energy, but that is a separate
`Attenuable` concern, deferred).

One generic quantity serves every discrete selector; the specific device
is told by `target_id` plus the `device_designation` tag, exactly as
`magnification` is one quantity reused across objectives and
`energy_position_curve` is one quantity reused across energy-driven axes.

Operating point keys:
  - `device_designation` (string, 1-100 chars): which selector this table
    is for (for example `"downstream_filter_paddle"`). Operator-supplied
    tag, redundant with `target_id` but self-describing in audit logs;
    mirrors `energy_position_curve.axis_designation` and
    `magnification.objective_designation`.

Value keys:
  - `points` (array, >= 2 items): the slots in selection order. The array
    index IS the slot index. Each item:
      - `name` (string, 1-100 chars): the human label for this slot (the
        foil material, the stripe coating, `"None"` for an empty slot).
        Documentary; the kernel keys on the array-order index.
      - `position` (number): the selector motor position for this slot. No
        inline unit annotation because the unit varies per device; the
        unit is documented by `position_unit` and is authoritative on the
        consuming `LookupTable.unit_out`.
  - `position_unit` (string, optional): the unit of the `position` values
    (for example `"mm"`); documentary, the consuming LookupTable's
    `unit_out` is the operative contract.
  - `provisional` (boolean, optional): true when the positions are
    placeholder values pending the real saved table from beamline staff.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "device_designation": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
    },
    "required": ["device_designation"],
    "additionalProperties": False,
}


def index_position_points(value: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    """Extract the (index, position) pairs from an index_position_table value.

    Returns the slots as `(independent, dependent)` float pairs: the slot
    INDEX (the array order, 0-based) is the independent variable, the motor
    position the dependent. The value dict has already passed `VALUE_SCHEMA`
    validation at append time (>= 2 points, each with a required name +
    position), so this reads the validated shape. The consuming
    `LookupTable` kernel owns snapping (`Nearest`); this helper only
    normalizes the payload into positional pairs, keying on the array order
    so the kernel stays decoupled from this quantity's schema. The `name`
    label is intentionally not surfaced here: it is documentary, carried in
    the calibration revision for audit, not used by the numeric kernel.
    """
    points = value["points"]
    return tuple((float(index), float(point["position"])) for index, point in enumerate(points))


VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                    },
                    "position": {
                        "type": "number",
                    },
                },
                "required": ["name", "position"],
                "additionalProperties": False,
            },
        },
        "position_unit": {
            "type": "string",
            "minLength": 1,
            "maxLength": 50,
        },
        "provisional": {
            "type": "boolean",
        },
    },
    "required": ["points"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA", "index_position_points"]
