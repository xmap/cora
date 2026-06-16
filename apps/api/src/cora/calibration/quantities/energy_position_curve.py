"""Energy-driven positioner curve: operating_point + value schemas.

The position a beamline positioner takes as a function of beam energy.
Selecting an energy moves several optics to energy-specific positions;
the monochromator crystal offset is the defining case (its position
picks the energy). The per-energy positions are established empirically
and saved (the beamline's saved-position tables), then interpolated for
energies between the saved points.

This is the catalog's FIRST curve-valued (relationship) quantity, and it
is shaped differently from the scalar siblings on purpose. A scalar
quantity (`magnification`, `rotation_center`, ...) carries a single
measured number AT an operating point, and treats `energy` as an
operating-point CONDITION ("magnification IS 9.83 when energy = 25"):
you read the value at the energy you are already at. Here the whole
point is the relationship ACROSS energy, evaluated to drive a motor to
ANY energy. So `energy` is the table's INDEPENDENT VARIABLE on the VALUE
side (a `points` array), and the operating_point only identifies WHICH
curve. One revision carries the whole curve so a `LookupTable` partition
rule can pin it by id and interpolate reproducibly. The name is "curve"
(not "table") to signal the continuous relationship the interpolation
realizes. Read-at-a-point and evaluate-across-a-range now coexist in the
catalog as two deliberate shapes.

One generic quantity serves every energy-driven axis; the specific axis
is told by `target_id` plus the `axis_designation` tag, exactly as
`magnification` is one quantity reused across objectives.

Operating point keys:
  - `axis_designation` (string, 1-100 chars): which positioner axis this
    curve is for (for example `"dmm_us_arm"`). Operator-supplied
    tag, redundant with `target_id` but self-describing in audit logs;
    mirrors `magnification.objective_designation`.
  - `beam_mode` (string, 1-100 chars, optional): the beam configuration
    the curve holds for (for example `"mono_Si_multilayer"`, `"white"`),
    so one axis can carry distinct curves per mode without colliding on
    the `(target_id, quantity, operating_point)` identity triple.

Value keys:
  - `points` (array, >= 2 items): the (energy, position) pairs defining
    the curve. At least two points are needed to interpolate. Each item:
      - `energy` (number, 1-100, multipleOf 0.001): the beam energy
        at this point, in keV. Same bounds + unit as the operating-point
        `energy` axis on the scalar quantities, for vocabulary uniformity.
      - `position` (number): the positioner position at this energy. No
        inline unit annotation because the unit varies per axis (mm for a
        linear stage, an angle for a rotary axis); the unit is documented
        by `position_unit` and is authoritative on the consuming
        `LookupTable.unit_out`.
  - `position_unit` (string, optional): the unit of the `position`
    values (for example `"mm"`); documentary, the consuming LookupTable's
    `unit_out` is the operative contract.
  - `provisional` (boolean, optional): true when the points are
    placeholder values pending the real saved per-energy table from
    beamline staff.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "axis_designation": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
        "beam_mode": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
    },
    "required": ["axis_designation"],
    "additionalProperties": False,
}

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
                    "energy": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 100,
                        "multipleOf": 0.001,
                        "unit": {"system": "udunits", "code": "keV"},
                    },
                    "position": {
                        "type": "number",
                    },
                },
                "required": ["energy", "position"],
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

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
