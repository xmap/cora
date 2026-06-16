"""Catalog descriptor: schema, validation, and loader.

The catalog descriptor (catalog/catalog.yaml) is the single human-readable
source for CORA's cross-facility vocabulary: Roles, Families, Capabilities,
Methods, Models, Assemblies. The docs build renders the Catalog pages from it.

Recipes are intentionally NOT a catalog kind. A Recipe (Recipe BC) is the
deployment-bound executable step sequence that hardcodes a beamline's device
addresses, so it is per-deployment, not cross-facility vocabulary; the portable
rung is the Method. Authored Recipes, if any, belong in the deployment docs.

Source-of-truth note (the no-drift boundary):
  - Roles and the closed enums (Affordance, ExecutorShape) are CODE-defined.
    This module mirrors the closed enums as frozensets to validate against, and
    a test asserts each mirror equals its `cora` enum. The Roles authored here
    are guarded by a test asserting they equal the code's SEED_ROLES.
  - Families, Capabilities, Methods, Models, Assemblies have no global code
    seed; this descriptor is their consolidated source, guarded by the
    round-trip test. An Assembly's id and content_hash are spine-computed, so
    the descriptor never authors them; sub-assembly links reference the child
    by name.

Zero cora.* imports by design: the docs build runs under a lean interpreter
that does not install the cora package. The enum mirrors below are kept honest
by the enum-equality tests, not by importing the enums here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# Mirrors of code-defined closed sets. Guarded by enum-equality tests against
# the cora enums; never edit these by hand without the test catching drift.
AFFORDANCES: frozenset[str] = frozenset(
    {
        "Rotatable",
        "Translatable",
        "Homeable",
        "Limitable",
        "Capturable",
        "Posable",
        "Indexable",
        "Following",
        "Leading",
        "Imageable",
        "Binnable",
        "Capturing",
        "Triggerable",
        "Gateable",
        "Synchronizable",
        "Marking",
        "Pulsing",
        "Streamable",
        "Bufferable",
        "Compressible",
        "Recording",
        "Coolable",
        "PIDControllable",
        "Shutterable",
        "Attenuable",
        "Bendable",
        "Identifiable",
        "Reportable",
        "Consumable",
    }
)
EXECUTOR_SHAPES: frozenset[str] = frozenset({"Method", "Procedure"})
MANUFACTURER_ID_TYPES: frozenset[str] = frozenset({"ROR", "GRID", "ISNI"})
SLOT_CARDINALITIES: frozenset[str] = frozenset(
    {"Exactly1", "ZeroOrOne", "OneOrMore", "ZeroOrMore"}
)

# Catalog models are closed-shape; forbid unknown keys so a mistyped field name
# (descripton, needed_familes) fails the build instead of silently rendering empty.
_MODEL_CONFIG = ConfigDict(extra="forbid", protected_namespaces=())


class CatalogError(ValueError):
    """The catalog descriptor is missing, unparseable, or fails validation."""


class Role(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    docstring: str
    required_affordances: list[str] = []
    optional_affordances: list[str] = []
    produces: list[str] = []
    consumes: list[str] = []

    @field_validator("required_affordances", "optional_affordances")
    @classmethod
    def _known_affordances(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - AFFORDANCES)
        if unknown:
            raise ValueError(f"unknown affordances: {unknown}")
        return value


class Family(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    note: str | None = None
    affordances: list[str] = []
    presents_as: list[str] = []
    settings_schema: dict[str, Any] | None = None

    @field_validator("affordances")
    @classmethod
    def _known_affordances(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - AFFORDANCES)
        if unknown:
            raise ValueError(f"unknown affordances: {unknown}")
        return value


class Capability(BaseModel):
    model_config = _MODEL_CONFIG

    code: str
    name: str
    description: str | None = None
    required_affordances: list[str] = []
    # Required non-empty: the closed-core contract (and define_capability) demand it.
    executor_shapes: list[str] = Field(min_length=1)
    parameters_schema: dict[str, Any] | None = None

    @field_validator("required_affordances")
    @classmethod
    def _known_affordances(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - AFFORDANCES)
        if unknown:
            raise ValueError(f"unknown affordances: {unknown}")
        return value

    @field_validator("executor_shapes")
    @classmethod
    def _known_shapes(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - EXECUTOR_SHAPES)
        if unknown:
            raise ValueError(f"unknown executor shapes: {unknown}")
        return value


class Method(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    capability: str | None = None
    purpose: str | None = None
    needed_families: list[str] = []
    needed_supplies: list[str] = []
    required_roles: list[str] = []
    parameters_schema: dict[str, Any] | None = None


class Manufacturer(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    identifier: str | None = None
    identifier_type: str | None = None

    @field_validator("identifier_type")
    @classmethod
    def _known_id_type(cls, value: str | None) -> str | None:
        if value is not None and value not in MANUFACTURER_ID_TYPES:
            raise ValueError(f"unknown manufacturer identifier_type: {value}")
        return value


class Model(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    manufacturer: Manufacturer
    part_number: str
    declared_families: list[str] = []


class TemplateSlot(BaseModel):
    model_config = _MODEL_CONFIG

    slot_name: str
    required_families: list[str] = Field(min_length=1)
    cardinality: str
    # Optional template defaults applied at instantiation unless overridden.
    # Both fold into the Assembly content_hash, so they are authorable here for
    # the same reason the other schema fields are; placement is a plain dict
    # (the descriptor has zero cora imports for the Placement type).
    default_settings: dict[str, Any] | None = None
    default_placement: dict[str, Any] | None = None

    @field_validator("cardinality")
    @classmethod
    def _known_cardinality(cls, value: str) -> str:
        if value not in SLOT_CARDINALITIES:
            raise ValueError(f"unknown slot cardinality: {value}")
        return value


class TemplateWire(BaseModel):
    model_config = _MODEL_CONFIG

    source_slot: str
    source_port: str
    target_slot: str
    target_port: str


class SubAssemblyLink(BaseModel):
    model_config = _MODEL_CONFIG

    slot_name: str
    # The child Assembly's NAME. The spine derives the child's id (uuid5 over
    # name) and content_hash at define time; authoring a hash here would be a
    # value the round-trip cannot guard, so the descriptor links by name.
    sub_assembly: str


class Assembly(BaseModel):
    model_config = _MODEL_CONFIG

    name: str
    note: str | None = None
    presents_as: list[str] = []
    required_slots: list[TemplateSlot] = []
    required_wires: list[TemplateWire] = []
    required_sub_assemblies: list[SubAssemblyLink] = []
    parameter_overrides_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class Catalog:
    """A validated catalog: the cross-facility vocabulary, in file order."""

    roles: list[Role]
    families: list[Family]
    capabilities: list[Capability]
    methods: list[Method]
    models: list[Model]
    assemblies: list[Assembly]


def load(path: str | Path) -> Catalog:
    """Read and validate the YAML catalog descriptor.

    Raises CatalogError (naming the path and field) on a missing file, a YAML
    parse error, or a schema violation.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogError(f"{path}: cannot read catalog: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CatalogError(f"{path}: top level must be a mapping")

    try:
        catalog = Catalog(
            roles=[Role.model_validate(r) for r in raw.get("roles", [])],
            families=[Family.model_validate(f) for f in raw.get("families", [])],
            capabilities=[Capability.model_validate(c) for c in raw.get("capabilities", [])],
            methods=[Method.model_validate(m) for m in raw.get("methods", [])],
            models=[Model.model_validate(m) for m in raw.get("models", [])],
            assemblies=[Assembly.model_validate(a) for a in raw.get("assemblies", [])],
        )
    except ValidationError as exc:
        raise CatalogError(f"{path}: catalog failed validation:\n{exc}") from exc

    _check_references(path, catalog)
    return catalog


def _check_references(path: Path, catalog: Catalog) -> None:
    """Within-catalog referential integrity: a typo in a method's capability or
    needed_families, a model's declared_families, or an assembly's slot
    families / presented roles / sub-assembly links, fails the build instead of
    rendering a dead in-page link or silently dropping a binding."""
    family_names = {f.name for f in catalog.families}
    capability_codes = {c.code for c in catalog.capabilities}
    for m in catalog.methods:
        if m.capability is not None and m.capability not in capability_codes:
            raise CatalogError(
                f"{path}: method '{m.name}' references unknown capability '{m.capability}'"
            )
        unknown = sorted(set(m.needed_families) - family_names)
        if unknown:
            raise CatalogError(f"{path}: method '{m.name}' needs unknown families {unknown}")
    for model in catalog.models:
        unknown = sorted(set(model.declared_families) - family_names)
        if unknown:
            raise CatalogError(f"{path}: model '{model.name}' declares unknown families {unknown}")

    role_names = {r.name for r in catalog.roles}
    assembly_names = {a.name for a in catalog.assemblies}
    for a in catalog.assemblies:
        unknown_roles = sorted(set(a.presents_as) - role_names)
        if unknown_roles:
            raise CatalogError(
                f"{path}: assembly '{a.name}' presents unknown roles {unknown_roles}"
            )
        leaf_slot_names = {s.slot_name for s in a.required_slots}
        for s in a.required_slots:
            unknown_fams = sorted(set(s.required_families) - family_names)
            if unknown_fams:
                raise CatalogError(
                    f"{path}: assembly '{a.name}' slot '{s.slot_name}' "
                    f"needs unknown families {unknown_fams}"
                )
        # Slots and sub-assembly link positions share one slot-name namespace
        # that must stay collision-free (a clash raises
        # SubAssemblySlotNameConflictError at define_assembly). Wires, however,
        # close over leaf slots ONLY (see the separate loop below), matching the
        # spine: a wire endpoint may not name a sub-assembly link position.
        slot_namespace = set(leaf_slot_names)
        for link in a.required_sub_assemblies:
            if link.sub_assembly not in assembly_names:
                raise CatalogError(
                    f"{path}: assembly '{a.name}' references unknown "
                    f"sub-assembly '{link.sub_assembly}'"
                )
            if link.slot_name in slot_namespace:
                raise CatalogError(
                    f"{path}: assembly '{a.name}' slot_name '{link.slot_name}' "
                    f"collides across slots and sub-assemblies"
                )
            slot_namespace.add(link.slot_name)
        for w in a.required_wires:
            for endpoint in (w.source_slot, w.target_slot):
                if endpoint not in leaf_slot_names:
                    raise CatalogError(
                        f"{path}: assembly '{a.name}' wire references "
                        f"unknown slot '{endpoint}'"
                    )
