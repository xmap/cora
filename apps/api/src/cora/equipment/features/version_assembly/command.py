"""The `VersionAssembly` command - intent dataclass for the version_assembly slice.

Replace-on-version semantics per the design memo: the command
carries the FULL canonical structural subset (the same fields
DefineAssembly carries, plus the target assembly_id), NOT a diff.
The decider replaces structure wholesale; the evolver folds the
new snapshot into state.

`presents_as_family_id` is mutable across versions because a
re-architected Assembly may stand in for a different Family
(e.g., DCM-revisited may move from `Monochromator` to a wider
`BeamConditioning` Family). The handler re-checks Family existence
for every referenced FamilyId (presents_as_family_id + every slot's
required_family_ids).

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
from cora.equipment.aggregates.assembly import TemplateSlot, TemplateWire


@dataclass(frozen=True)
class VersionAssembly:
    """Publish a new revision snapshot of an existing Assembly."""

    assembly_id: UUID
    name: str
    presents_as_family_id: UUID
    required_slots: frozenset[TemplateSlot] = field(default_factory=frozenset[TemplateSlot])
    required_wires: frozenset[TemplateWire] = field(default_factory=frozenset[TemplateWire])
    parameter_overrides_schema: dict[str, Any] | None = None
    drawing: Drawing | None = None
    version: str | None = None
