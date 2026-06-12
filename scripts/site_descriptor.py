"""Site descriptor: schema, validation, and loader.

The site descriptor (deployments/aps/site.yaml) is the single human-readable
source for one facility's site-level surface: the Facility itself, the Practices
registered there, and the facility principals (Actors and Agents). The docs
build renders the APS site pages from it.

Source-of-truth note (the no-drift boundary):
  - The closed enums (FacilityKind, ActorKind) are CODE-defined. This module
    mirrors them as frozensets to validate against, and a test asserts each
    mirror equals its `cora` enum.
  - Agents (RunDebriefer, CautionDrafter) are CODE-SEEDED at app startup; a
    drift-guard test asserts the agents authored here equal the seed constants
    (name, kind, version, model provider/name).
  - The Facility (self facility) is bootstrap-seeded with invariants only
    (kind=Site, display_name == code); a light test asserts those invariants.
  - Practices and Actors have no global code seed (they live only in
    integration-test scenarios), so this descriptor is their consolidated
    source, guarded by the round-trip test only.

Zero cora.* imports by design: the docs build runs under a lean interpreter
that does not install the cora package. The enum mirrors below are kept honest
by the enum-equality tests, not by importing the enums here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

# Mirrors of code-defined closed sets. Guarded by enum-equality tests against
# the cora enums; never edit these by hand without the test catching drift.
FACILITY_KINDS: frozenset[str] = frozenset({"Site", "Area"})
ACTOR_KINDS: frozenset[str] = frozenset({"human", "agent", "service_account"})

# Site models are closed-shape; forbid unknown keys so a mistyped field name
# fails the build instead of silently rendering empty.
_MODEL_CONFIG = ConfigDict(extra="forbid")
# Agent carries model_provider / model_name; opt out of pydantic's protected
# "model_" namespace so those self-describing field names do not warn.
_AGENT_MODEL_CONFIG = ConfigDict(extra="forbid", protected_namespaces=())


class SiteError(ValueError):
    """The site descriptor is missing, unparseable, or fails validation."""


class SiteFacility(BaseModel):
    model_config = _MODEL_CONFIG

    code: str
    display_name: str
    kind: str
    institution: str | None = None
    sectors: list[str] = []
    beamlines: list[str] = []
    note: str | None = None

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in FACILITY_KINDS:
            raise ValueError(f"unknown facility kind: {value}")
        return value


class Practice(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    method: str
    pending: bool = False
    note: str | None = None


class Actor(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    kind: str
    pending: bool = False
    note: str | None = None

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in ACTOR_KINDS:
            raise ValueError(f"unknown actor kind: {value}")
        return value


class Agent(BaseModel):
    model_config = _AGENT_MODEL_CONFIG

    name: str
    kind: str
    version: str
    model_provider: str
    model_name: str
    pending: bool = False
    note: str | None = None


class Supply(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    kind: str
    pending: bool = False
    note: str | None = None


class Clearance(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    kind: str
    binding: str | None = None
    pending: bool = False
    note: str | None = None


class Caution(BaseModel):
    model_config = _MODEL_CONFIG

    target: str
    text: str
    category: str | None = None
    severity: str | None = None
    pending: bool = False
    note: str | None = None


@dataclass(frozen=True)
class Site:
    """A validated site: one facility's site-level surface, in file order."""

    facility: SiteFacility
    practices: list[Practice]
    actors: list[Actor]
    agents: list[Agent]
    supplies: list[Supply]
    clearances: list[Clearance]
    cautions: list[Caution]


def load(path: str | Path) -> Site:
    """Read and validate the YAML site descriptor.

    Raises SiteError (naming the path and field) on a missing file, a YAML
    parse error, or a schema violation.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SiteError(f"{path}: cannot read site: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SiteError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise SiteError(f"{path}: top level must be a mapping")

    if "facility" not in raw:
        raise SiteError(f"{path}: missing required 'facility' section")

    try:
        site = Site(
            facility=SiteFacility.model_validate(raw["facility"]),
            practices=[Practice.model_validate(p) for p in raw.get("practices", [])],
            actors=[Actor.model_validate(a) for a in raw.get("actors", [])],
            agents=[Agent.model_validate(a) for a in raw.get("agents", [])],
            supplies=[Supply.model_validate(s) for s in raw.get("supplies", [])],
            clearances=[Clearance.model_validate(c) for c in raw.get("clearances", [])],
            cautions=[Caution.model_validate(c) for c in raw.get("cautions", [])],
        )
    except ValidationError as exc:
        raise SiteError(f"{path}: site failed validation:\n{exc}") from exc

    _check_references(path, site)
    return site


def _check_references(path: Path, site: Site) -> None:
    """Within-site integrity: duplicate practice / actor / agent names are a
    copy-paste mistake that would render two rows for the same thing, so reject
    them at build time rather than silently double-listing."""
    for label, names in (
        ("practice", [p.name for p in site.practices]),
        ("actor", [a.name for a in site.actors]),
        ("agent", [a.name for a in site.agents]),
        ("supply", [s.name for s in site.supplies]),
        ("clearance", [c.name for c in site.clearances]),
        ("caution", [c.text for c in site.cautions]),
    ):
        seen: set[str] = set()
        for name in names:
            if name in seen:
                raise SiteError(f"{path}: duplicate {label} name '{name}'")
            seen.add(name)
