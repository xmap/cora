"""Slit-blade throw scale calibration: operating_point + value schemas.

The blade-throw scale is the per-blade conversion between blade motion
(millimetres commanded) and the beam-edge shift it produces on the
detector (pixels). Measured by the `blade_throw_characterization`
Procedure: drive each blade by a known throw, measure the bright-spot
edge shift, and fit the slope. An outlier blade flags a mis-calibrated
motor.

Operating point keys:
  - `optics_config` (string): the optical magnification config in use
    (lens position, scintillator-detector geometry). The scale is a
    geometric pixels-per-mm figure set by the imaging magnification, so
    the same slit at different optics gets distinct revision chains. No
    `energy` key: the scale does not depend on beam energy. String tag
    rather than a numeric magnification, matching `rotation_center`:
    operators name configs ("5x", "10x") and the same numeric value can
    mean different physical configs across upgrades.

Value keys:
  - `blades` (array, 1-4 entries): one entry per driven blade, each with
    a `blade` name (for example "top", "bottom", "inboard", "outboard")
    and a `scale` (pixels of edge shift per mm of blade motion, > 0).
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "optics_config": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
    },
    "required": ["optics_config"],
    "additionalProperties": False,
}

VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "blades": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "blade": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 50,
                    },
                    "scale": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "unit": {"system": "udunits", "code": "pixel/mm"},
                    },
                },
                "required": ["blade", "scale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["blades"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
