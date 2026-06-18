"""Monochromator energy-offset calibration: operating_point + value schemas.

The signed correction between the energy the monochromator is commanded
to deliver and the true energy it actually delivers. Measured by rocking
a crystal of known lattice spacing (a channel-cut crystal) through its
Bragg peak, fitting the peak angle, and applying Bragg's law to recover
the true energy; the offset is `true - commanded`. The same correction
re-derived at a second energy confirms it is constant (linear), which is
why this is a scalar offset rather than a fitted slope.

This records the correction in the ENERGY domain, on the axis the
operator commands, so the consumer applies it at the energy-command seam:
to deliver a true energy E, command `E - offset`. The energy-to-position
relationship of the driven optics stays a separate concern, carried by
the `energy_position_curve` quantity; this offset does not modify those
curves. It is the same shape NeXus `NXcalibration` records as its linear
model (`calibrated = original + offset`, with `physical_quantity` energy);
a scaling term is intentionally omitted until a beamline needs one, when
it can be added as an additive optional value key.

The Calibration `target_id` is the monochromator Asset (the calibrated
entity), not the crystal (the measuring tool); the crystal and the fitted
Bragg evidence live in the producing Procedure's step logbook.

Operating point keys:
  - `energy` (number, 1-100, multipleOf 0.001): the commanded beam energy
    at which the offset was measured, in keV. The offset depends weakly on
    energy in practice, so the same monochromator at different commanded
    energies gets distinct revision chains, mirroring `rotation_center`.
  - `beam_mode` (string, 1-100 chars): the beam configuration the offset
    holds for (for example `"mono"`). Energy calibration is a
    monochromatic-mode operation; the key keeps the identity triple
    explicit and consistent with `energy_position_curve`.

Value keys:
  - `offset` (number): the signed energy correction `true - commanded`,
    in keV. May be negative; not bounded, since it is a small residual.
  - `uncertainty` (number, optional, minimum 0): operator- or fit-supplied
    1-sigma uncertainty in keV; if absent, downstream consumers treat as
    unknown.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "energy": {
            "type": "number",
            "minimum": 1,
            "maximum": 100,
            "multipleOf": 0.001,
            "unit": {"system": "udunits", "code": "keV"},
        },
        "beam_mode": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
    },
    "required": ["energy", "beam_mode"],
    "additionalProperties": False,
}

VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "offset": {
            "type": "number",
            "unit": {"system": "udunits", "code": "keV"},
        },
        "uncertainty": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "keV"},
        },
    },
    "required": ["offset"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
