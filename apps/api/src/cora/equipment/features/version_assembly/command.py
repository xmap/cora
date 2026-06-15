"""The `VersionAssembly` command - intent dataclass for the version_assembly slice.

Replace-on-version semantics per the design memo: the command
carries the FULL canonical structural subset (the same fields
DefineAssembly carries, plus the target assembly_id), NOT a diff.
The decider replaces structure wholesale; the evolver folds the
new snapshot into state.

`presents_as` is replaced on version: a re-architected Assembly may
advertise a different set of Role contracts. The handler re-checks
that every RoleId in `presents_as` resolves to a defined Role, and
that every slot's required_family_ids resolves to a defined Family.

Multi-source FSM transition: Defined -> Versioned AND
Versioned -> Versioned are both valid; only Deprecated rejects.

Re-attestation: the same structural content (yielding the same
content_hash) emits a fresh AssemblyVersioned event. Re-attesting
is a legitimate audit moment (`operator confirmed v2 again on date
X`); the decider does not refuse it.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates.assembly import SubAssemblyLink, TemplateSlot, TemplateWire


@dataclass(frozen=True)
class VersionAssembly:
    """Publish a new revision snapshot of an existing Assembly."""

    assembly_id: UUID
    name: str
    presents_as: frozenset[UUID] = field(default_factory=frozenset[UUID])
    required_slots: frozenset[TemplateSlot] = field(default_factory=frozenset[TemplateSlot])
    required_wires: frozenset[TemplateWire] = field(default_factory=frozenset[TemplateWire])
    required_sub_assemblies: frozenset[SubAssemblyLink] = field(
        default_factory=frozenset[SubAssemblyLink]
    )
    parameter_overrides_schema: dict[str, Any] | None = None
    drawing: Drawing | None = None
    version: str | None = None
