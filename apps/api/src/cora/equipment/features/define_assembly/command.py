"""The `DefineAssembly` command - intent dataclass for the define_assembly slice.

Carries the caller-controlled structural fields: name,
presents_as_family_id, required_slots, required_wires, the optional
parameter_overrides_schema, the optional drawing, and the optional
operator-curatorial version label.

Server-side concerns (new assembly_id, wall-clock timestamp,
correlation id, per-event ids, computed content_hash) are injected
by the handler from infrastructure ports or computed pre-emit.

Slots and wires arrive as fully-constructed domain VOs (the route
layer's TemplateSlotBody / TemplateWireBody call .to_domain() before
the command is built); structural VO-level invariants (slot-name
length, cardinality enum membership, non-empty required_family_ids,
wire-port-name length, degenerate-full-self-loop rejection, wire-
endpoints-reference-declared-slots closure via Assembly.__post_init__
when state is constructed in the evolver) all fire at VO construction
or evolver-fold time, NOT inside the decider.

Cross-aggregate references checked by the handler before the decider:
  - presents_as_family_id must resolve to a defined Family.
  - Every FamilyId in every slot's required_family_ids must resolve.

Cross-aggregate references NOT checked:
  - Asset existence (Assembly is a template; the Assets do not exist
    yet at define time). instantiate_assembly checks Asset existence
    when it lands.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates.assembly import TemplateSlot, TemplateWire


@dataclass(frozen=True)
class DefineAssembly:
    """Define a new Assembly composition blueprint."""

    name: str
    presents_as_family_id: UUID
    required_slots: frozenset[TemplateSlot] = field(default_factory=frozenset[TemplateSlot])
    required_wires: frozenset[TemplateWire] = field(default_factory=frozenset[TemplateWire])
    parameter_overrides_schema: dict[str, Any] | None = None
    drawing: Drawing | None = None
    version: str | None = None
