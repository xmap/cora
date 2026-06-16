"""Closed catalog of `CalibrationQuantity` values + per-quantity schema registry.

Each quantity in the closed StrEnum declares two JSON Schemas at module
import time:

  - `OPERATING_POINT_SCHEMA` — what operating-conditions dict identifies
    this calibration (for example, rotation_center at `{energy: 25,
    optics_config: "5x"}` is distinct from the same quantity at 30 keV).
  - `VALUE_SCHEMA` — what value dict the revision carries (for example,
    `{center: 1024.5, uncertainty: 0.3}`).

Both schemas are CLOSED (`additionalProperties: False`) and property-
type-restricted to primitives per Q1 lock (Round 2: NXcalibration's
free-form approach is a documented gap; RELION optics-group + DICOM
coded-content + CMS typed-metadata all converge on typed-at-contract).

## Adding a quantity

1. Add the StrEnum value below.
2. Add a sibling module `cora/calibration/quantities/<value>.py` exposing
   `OPERATING_POINT_SCHEMA` + `VALUE_SCHEMA`.
3. Add the module to `_SCHEMAS_BY_QUANTITY` below.
4. Add the affordance unit test pinning the count + the per-quantity
   schema round-trip.

Closed-catalog growth via PR (matches Affordance enum precedent).
Runtime configuration is forbidden per the design memo anti-hook
on free-dict operating-point: every quantity must declare schemas
before being usable.
"""

from enum import StrEnum
from typing import Any

from cora.calibration.quantities import (
    detector_pixel_size,
    effective_thickness,
    energy_position_curve,
    index_position_table,
    magnification,
    rotation_center,
)


class CalibrationQuantity(StrEnum):
    """Closed catalog of supported calibration quantities.

    Day-one set covers the 2-BM tomography pilot's load-bearing
    calibrations. Growth happens by PR per the Affordance enum precedent.

    String values are stable-by-design (event payloads carry them
    verbatim); renaming a value would orphan stored events. The enum
    member name follows SCREAMING_SNAKE_CASE; the value follows
    snake_case to match jsonb-key conventions in operating_point and
    value dicts.
    """

    ROTATION_CENTER = "rotation_center"
    DETECTOR_PIXEL_SIZE = "detector_pixel_size"
    MAGNIFICATION = "magnification"
    EFFECTIVE_THICKNESS = "effective_thickness"
    ENERGY_POSITION_CURVE = "energy_position_curve"
    INDEX_POSITION_TABLE = "index_position_table"


# Per-quantity schema registry (built at import time)
_SCHEMAS_BY_QUANTITY: dict[CalibrationQuantity, tuple[dict[str, Any], dict[str, Any]]] = {
    CalibrationQuantity.ROTATION_CENTER: (
        rotation_center.OPERATING_POINT_SCHEMA,
        rotation_center.VALUE_SCHEMA,
    ),
    CalibrationQuantity.DETECTOR_PIXEL_SIZE: (
        detector_pixel_size.OPERATING_POINT_SCHEMA,
        detector_pixel_size.VALUE_SCHEMA,
    ),
    CalibrationQuantity.MAGNIFICATION: (
        magnification.OPERATING_POINT_SCHEMA,
        magnification.VALUE_SCHEMA,
    ),
    CalibrationQuantity.EFFECTIVE_THICKNESS: (
        effective_thickness.OPERATING_POINT_SCHEMA,
        effective_thickness.VALUE_SCHEMA,
    ),
    CalibrationQuantity.ENERGY_POSITION_CURVE: (
        energy_position_curve.OPERATING_POINT_SCHEMA,
        energy_position_curve.VALUE_SCHEMA,
    ),
    CalibrationQuantity.INDEX_POSITION_TABLE: (
        index_position_table.OPERATING_POINT_SCHEMA,
        index_position_table.VALUE_SCHEMA,
    ),
}


def get_operating_point_schema(quantity: CalibrationQuantity) -> dict[str, Any]:
    """Return the operating_point JSON Schema for the named quantity.

    Raises KeyError if the quantity has no registered schema (which is
    a programmer error: the StrEnum + registry must move together).
    """
    return _SCHEMAS_BY_QUANTITY[quantity][0]


def get_value_schema(quantity: CalibrationQuantity) -> dict[str, Any]:
    """Return the value JSON Schema for the named quantity."""
    return _SCHEMAS_BY_QUANTITY[quantity][1]


__all__ = [
    "CalibrationQuantity",
    "get_operating_point_schema",
    "get_value_schema",
]
