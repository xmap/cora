"""Assembly aggregate: the composition blueprint for a reusable cluster of Assets.

An `Assembly` declares `required_slots` (Family-typed, cardinality-
annotated, optionally pre-Placed) and `required_wires` (slot-keyed
4-tuples), and exposes a stable `presents_as_family_id` so other
aggregates (Method.needed_families, Capability bindings) can treat
an instantiated Assembly as one typed unit at the same level as a
single Asset.

Content-addressed: `content_hash` is the SHA-256 hex fingerprint of
the canonical subset {name, presents_as_family_id, required_slots,
required_wires, parameter_overrides_schema}. Two operators
independently authoring the same Assembly converge on the same
content_hash.

Lifecycle: `Defined | Versioned | Deprecated`. Multiple
AssemblyVersioned events per stream (append-only revisions).

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_assembly/` (define / version /
deprecate / instantiate); this scaffold ships the aggregate
kernel without any wired slices.
"""

from cora.equipment.aggregates.assembly.events import (
    AssemblyDefined,
    AssemblyDeprecated,
    AssemblyEvent,
    AssemblyVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.assembly.evolver import evolve, fold
from cora.equipment.aggregates.assembly.read import load_assembly
from cora.equipment.aggregates.assembly.state import (
    ASSEMBLY_NAME_MAX_LENGTH,
    SLOT_NAME_MAX_LENGTH,
    WIRE_PORT_NAME_MAX_LENGTH,
    Assembly,
    AssemblyAlreadyExistsError,
    AssemblyCannotDeprecateError,
    AssemblyCannotInstantiateError,
    AssemblyCannotVersionError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    FamilyNotFoundForAssemblyError,
    FixtureAssetFamilyMismatchError,
    FixtureAssetNotAttachableError,
    FixtureAssetNotFoundError,
    FixtureAssetNotInstalledError,
    FixtureMappingIncompleteError,
    FixtureParameterOverridesInvalidError,
    InvalidAssemblyNameError,
    InvalidParameterOverridesSchemaError,
    InvalidSlotCardinalityError,
    InvalidSlotNameError,
    InvalidTemplateSlotError,
    InvalidWireSpecError,
    SlotCardinality,
    SlotName,
    TemplateSlot,
    TemplateWire,
    WireReferencesUnknownSlotError,
)

__all__ = [
    "ASSEMBLY_NAME_MAX_LENGTH",
    "SLOT_NAME_MAX_LENGTH",
    "WIRE_PORT_NAME_MAX_LENGTH",
    "Assembly",
    "AssemblyAlreadyExistsError",
    "AssemblyCannotDeprecateError",
    "AssemblyCannotInstantiateError",
    "AssemblyCannotVersionError",
    "AssemblyDefined",
    "AssemblyDeprecated",
    "AssemblyEvent",
    "AssemblyName",
    "AssemblyNotFoundError",
    "AssemblyStatus",
    "AssemblyVersioned",
    "FamilyNotFoundForAssemblyError",
    "FixtureAssetFamilyMismatchError",
    "FixtureAssetNotAttachableError",
    "FixtureAssetNotFoundError",
    "FixtureAssetNotInstalledError",
    "FixtureMappingIncompleteError",
    "FixtureParameterOverridesInvalidError",
    "InvalidAssemblyNameError",
    "InvalidParameterOverridesSchemaError",
    "InvalidSlotCardinalityError",
    "InvalidSlotNameError",
    "InvalidTemplateSlotError",
    "InvalidWireSpecError",
    "SlotCardinality",
    "SlotName",
    "TemplateSlot",
    "TemplateWire",
    "WireReferencesUnknownSlotError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_assembly",
    "to_payload",
]
