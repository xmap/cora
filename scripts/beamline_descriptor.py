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

# The three badge axes every beamline declares. Orthogonal by design: maturity
# is CORA's relationship to the beamline, evidence is where the facts came from,
# coverage is how complete the modelled slice is. Each is a closed vocabulary,
# guarded by an enum-mirror test so it cannot silently grow, and by a cross-axis
# consistency test so the combinations stay logical.

# maturity: CORA's relationship to the beamline.
#   pilot  - CORA drives it live (the operational pilot).
#   design - on CORA's roadmap, pre-live, modelled from design documents ahead
#            of build or recommissioning.
#   model  - off-roadmap generalization exercise on an operating beamline.
MATURITIES: frozenset[str] = frozenset({"pilot", "design", "model"})

# evidence: provenance tier of the facts, strongest to weakest.
#   live            - verified against the running instrument.
#   design_report   - a staff-authored technical or final design report.
#   controls_config - public machine-readable controls with real per-device
#                     handles (dodal, bluesky profiles, DESY OnlineXML, ESRF
#                     BLISS Beacon, MXCuBE HardwareObjects, eco / slic, pcdshub).
#   narrative       - facility pages or papers only; families inferred, no
#                     per-device control handles.
EVIDENCE_TIERS: frozenset[str] = frozenset(
    {"live", "design_report", "controls_config", "narrative"}
)

# coverage: completeness of the modelled scope.
#   full    - the modelled slice is the whole operational core.
#   partial - a deliberately incomplete cut of the device or physics model.
COVERAGES: frozenset[str] = frozenset({"full", "partial"})

# Documentation tier: whether the beamline's reader page set is generated from
# this descriptor ("model") or hand-authored as a rich operational set with only
# the Source walk generated ("pilot", the live-driven 2-BM / FXI).
DEPLOYMENT_TIERS: frozenset[str] = frozenset({"model", "pilot"})

# Page layout: how a model-tier beamline's generated reader set is shaped.
#   walk   - the default: a Source page at beamline.md, an inventory.md reference,
#            and the Sample / Detector / Controls pages under equipment/, wrapped
#            in a "Walk the beam" nav group.
#   stages - Inventory dissolved into the stages: flat source.md / sample.md /
#            detector.md / controls.md siblings, no equipment/ folder, no
#            inventory.md, nav flattened. The SRX pilot for this shape.
PAGE_LAYOUTS: frozenset[str] = frozenset({"walk", "stages"})

# The beam-path stages every subsystem group declares. Closed and generalizable
# across beamlines: the source delivers the incident beam, the sample holds the
# specimen, detection records the signal. Each group maps to exactly one.
BEAM_PATH_STAGES: tuple[str, ...] = ("source", "sample", "detection")

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
    """A subsystem stop on the beam walk: a list of devices plus framing.

    Every group declares its `stage` (source, sample, or detection), the
    generalizable three-act decomposition the Hardware page renders around.
    """

    model_config = _MODEL_CONFIG

    stage: str
    enclosure: str | None = None
    intro: str | None = None
    note: str | None = None
    devices: list[Device] = []
    decommissioned: list[str] = []  # provenance only; typed list[str] forbids a device-dict here

    @field_validator("stage")
    @classmethod
    def _known_stage(cls, value: str) -> str:
        if value not in BEAM_PATH_STAGES:
            raise ValueError(f"unknown stage {value!r}; expected one of {list(BEAM_PATH_STAGES)}")
        return value


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




class SourceRef(BaseModel):
    """The public source the beamline's facts were read from.

    A verifiable pointer to the profile collection, device layer, or facility
    document a reverse-engineered beamline was extracted from, surfaced in the
    generated-from banner. Absent for beamlines with no single documented
    source (e.g. the live operational pilot).
    """

    model_config = _MODEL_CONFIG

    label: str
    url: str


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
    maturity: str
    evidence: str
    coverage: str
    # One-line description of what the beamline is, in the fleet's own voice
    # (technique + notable kit + fleet role). The single source for the
    # "What it is" cell on the deployments landing page and the beamline's row
    # in its Site facility-page roster, so the two never drift. Optional in the
    # schema so a descriptor loads mid-authoring; a fitness test requires it.
    summary: str | None = None
    # Which documentation tier this beamline's page set uses. "model" (the
    # default) means the whole reader set is generated from this descriptor
    # (index, inventory, beam-walk); "pilot" means CORA drives it live and its
    # rich operational pages (recipes, procedures, operations, experiment) are
    # hand-authored, so only the Source walk is generated. Set "pilot" on 2-BM
    # and FXI; every other beamline is "model".
    deployment_tier: str = "model"
    # How the generated reader set is shaped: "walk" (the default, Source +
    # inventory + equipment/ pages under a "Walk the beam" group) or "stages"
    # (Inventory dissolved into flat source/sample/detector/controls siblings).
    page_layout: str = "walk"
    # One-line defining-shape sentence: what makes this beamline distinct (its
    # measurement shape, the new thing it brings to the fleet), rendered as the
    # lead of the generated index's beamline section. The one bespoke line no
    # descriptor field reconstructs; kept to a single sentence, not a paragraph.
    shape: str | None = None
    # The public source the facts were read from (profile collection, device
    # layer, or facility document), surfaced in the generated-from banner.
    # Absent for beamlines with no single documented source (the live pilot).
    source_ref: SourceRef | None = None

    @field_validator("z_span_mm")
    @classmethod
    def _two_endpoints(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(value) != 2:
            raise ValueError("z_span_mm must be exactly [start, end]")
        return value

    @field_validator("deployment_tier")
    @classmethod
    def _known_deployment_tier(cls, value: str) -> str:
        if value not in DEPLOYMENT_TIERS:
            raise ValueError(
                f"unknown deployment_tier {value!r}; expected one of {sorted(DEPLOYMENT_TIERS)}"
            )
        return value

    @field_validator("page_layout")
    @classmethod
    def _known_page_layout(cls, value: str) -> str:
        if value not in PAGE_LAYOUTS:
            raise ValueError(
                f"unknown page_layout {value!r}; expected one of {sorted(PAGE_LAYOUTS)}"
            )
        return value

    @field_validator("maturity")
    @classmethod
    def _known_maturity(cls, value: str) -> str:
        if value not in MATURITIES:
            raise ValueError(f"unknown maturity {value!r}; expected one of {sorted(MATURITIES)}")
        return value

    @field_validator("evidence")
    @classmethod
    def _known_evidence(cls, value: str) -> str:
        if value not in EVIDENCE_TIERS:
            raise ValueError(
                f"unknown evidence {value!r}; expected one of {sorted(EVIDENCE_TIERS)}"
            )
        return value

    @field_validator("coverage")
    @classmethod
    def _known_coverage(cls, value: str) -> str:
        if value not in COVERAGES:
            raise ValueError(f"unknown coverage {value!r}; expected one of {sorted(COVERAGES)}")
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
