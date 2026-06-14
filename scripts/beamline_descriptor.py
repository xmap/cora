"""Beamline descriptor: schema, validation, and loader.

A beamline descriptor (deployments/<id>/beamline.yaml) is the single
human-readable source describing one beamline as a walk along the beam,
source to detector, grouped by subsystem. This module defines its shape
(Pydantic v2 models) and a `load()` that reads the YAML and validates it.

Single source of truth for the schema, used by three consumers:

  1. scripts/beamline_pages.py renders a docs page from it at docs build
     time (via the on_files hook in scripts/mkdocs_hooks.py).
  2. The integration tests load it (dynamic-import, mirroring how
     apps/api/tests/integration/scenarios/conftest.py loads scenarios_meta).
  3. A future CORA seeder will reconcile it into the event store.

Zero cora.* imports by design: the docs build runs under a lean interpreter
that does not install the cora package.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

# Top-level keys that are not beam-path groups. Everything else at the top
# level is a subsystem group, kept in file order (the authored beam-path order).
KNOWN_TOP_KEYS: frozenset[str] = frozenset({"beamline", "enclosures", "controls", "resources"})

# Mirror of the code's DrawingSystem enum; guarded by an enum-equality test.
DRAWING_SYSTEMS: frozenset[str] = frozenset({"ICMS", "EDMS", "DOI"})

_MODEL_CONFIG = ConfigDict(extra="allow", protected_namespaces=())


class DescriptorError(ValueError):
    """A descriptor file is missing, unparseable, or fails validation.

    Carries the descriptor path so the docs build (mkdocs --strict) and the
    tests both fail with a message that names the file and the offending field.
    """


class Drawing(BaseModel):
    """An engineering-document reference (ISO 7200 system / number / revision)."""

    model_config = _MODEL_CONFIG

    system: str
    number: str
    revision: str | None = None

    @field_validator("system")
    @classmethod
    def _known_system(cls, value: str) -> str:
        if value not in DRAWING_SYSTEMS:
            raise ValueError(f"unknown drawing system: {value}")
        return value


class Calibration(BaseModel):
    """An empirical calibration record attached to a device."""

    model_config = _MODEL_CONFIG

    name: str | None = None
    quantity: str
    operating_point: dict[str, Any] | None = None
    value: Any = None
    source: str | None = None
    status: str | None = None


class Device(BaseModel):
    """One physical thing on (or beside) the beam.

    Structural fields are declared; everything else (range, material, speed,
    sensor, ...) is an open key-spec captured in `model_extra` and rendered as
    the device's specs.
    """

    model_config = _MODEL_CONFIG

    name: str
    family: str | None = None
    pv: str | dict[str, Any] | None = None
    model: str | None = None
    controller: str | None = None
    enclosure: str | None = None
    replaceable: bool = False
    passive: bool = False
    new: bool = False
    confirm: bool | str = False
    note: str | None = None
    drawing: Drawing | None = None
    calibrations: list[Calibration] = []
    constituents: list[Device] | None = None


class Group(BaseModel):
    """A subsystem stop on the beam walk: a list of devices plus framing."""

    model_config = _MODEL_CONFIG

    enclosure: str | None = None
    intro: str | None = None
    note: str | None = None
    devices: list[Device] = []


class Enclosure(BaseModel):
    """An access-gated volume (a hutch, cabin, vault, room) that gates work.

    `facility_code` is the containing geography: the Site / Area slug the
    enclosure sits within (a space inside a larger space), not an equipment
    pointer. `permit_signal` carries the personnel-safety permit handle when
    known, or a `confirm` note when it is still an operator-confirm item.
    """

    model_config = _MODEL_CONFIG

    name: str
    role: str | None = None
    facility_code: str | None = None
    permit_signal: str | dict[str, Any] | None = None


class Beamline(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    facility: str | None = None
    sector: str | None = None
    tier: str | None = None
    parent: str | None = None
    drawing: str | None = None
    source: str | None = None
    z_span_mm: list[int] | None = None

    @field_validator("z_span_mm")
    @classmethod
    def _two_endpoints(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(value) != 2:
            raise ValueError("z_span_mm must be exactly [start, end]")
        return value


class Controls(BaseModel):
    """Cross-cutting drive electronics and trigger hardware."""

    model_config = _MODEL_CONFIG

    intro: str | None = None
    motion_controllers: list[Device] = []
    triggering: list[Device] = []
    software_iocs_not_modeled: list[str] = []


class Resources(BaseModel):
    """Cross-cutting supplies and the replaceable-parts inventory."""

    model_config = _MODEL_CONFIG

    intro: str | None = None
    supplies: list[dict[str, Any]] = []
    replaceable_parts: dict[str, list[str]] = {}


@dataclass(frozen=True)
class BeamlineDescriptor:
    """A validated descriptor: the beamline, its enclosures, the ordered
    beam-path groups, and the two cross-cutting sections."""

    beamline: Beamline
    enclosures: list[Enclosure]
    groups: list[tuple[str, Group]]
    controls: Controls | None
    resources: Resources | None


def load(path: str | Path) -> BeamlineDescriptor:
    """Read and validate a YAML beamline descriptor.

    Raises DescriptorError (naming the path and field) on a missing file, a
    YAML parse error, or a schema violation.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DescriptorError(f"{path}: cannot read descriptor: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DescriptorError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise DescriptorError(f"{path}: top level must be a mapping")

    if "beamline" not in raw:
        raise DescriptorError(f"{path}: missing required top-level key 'beamline'")

    try:
        beamline = Beamline.model_validate(raw["beamline"])
        enclosures = [Enclosure.model_validate(e) for e in raw.get("enclosures", [])]
        controls = Controls.model_validate(raw["controls"]) if "controls" in raw else None
        resources = Resources.model_validate(raw["resources"]) if "resources" in raw else None
        groups = [
            (key, Group.model_validate(value))
            for key, value in raw.items()
            if key not in KNOWN_TOP_KEYS
        ]
    except ValidationError as exc:
        raise DescriptorError(f"{path}: descriptor failed validation:\n{exc}") from exc

    declared = {enclosure.name for enclosure in enclosures}
    for key, group in groups:
        refs = [group.enclosure] + [device.enclosure for device in group.devices]
        for ref in refs:
            if ref is not None and ref not in declared:
                raise DescriptorError(
                    f"{path}: group '{key}' names enclosure '{ref}', "
                    f"which is not a declared enclosure {sorted(declared)}"
                )

    return BeamlineDescriptor(
        beamline=beamline,
        enclosures=enclosures,
        groups=groups,
        controls=controls,
        resources=resources,
    )
