"""Shared Pydantic wire-format mirror of the `TemplateSlot` value object.

`TemplateSlot` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates.assembly.state`). This body is the wire
shape REST and MCP parse, with `to_domain()` converting to the
domain VO (which may raise `InvalidSlotNameError`,
`InvalidSlotCardinalityError`, `InvalidTemplateSlotError`, or
`InvalidPlacementError` during construction).

Pydantic enforces field-shape rules at the API boundary; domain
invariants (non-empty `required_family_ids`, closed-enum
`cardinality`, NaN-rejecting `default_placement`) surface from the
domain VO constructors and map to HTTP 400 through the BC's
exception handler.

Hoisted alongside `PlacementBody` / `DrawingBody` since both the
REST route and the MCP tool for `define_assembly` (and the future
`version_assembly` slice) parse the same shape.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from cora.equipment._placement_body import PlacementBody
from cora.equipment.aggregates.assembly.state import (
    SLOT_NAME_MAX_LENGTH,
    SlotCardinality,
    SlotName,
    TemplateSlot,
)


class TemplateSlotBody(BaseModel):
    """Wire format for a TemplateSlot value object."""

    slot_name: str = Field(
        ...,
        min_length=1,
        max_length=SLOT_NAME_MAX_LENGTH,
        description=(
            "Canonical name of this slot within the Assembly "
            "(e.g., 'camera', 'rotary', 'trigger_source')."
        ),
    )
    required_family_ids: frozenset[UUID] = Field(
        ...,
        min_length=1,
        description=(
            "Set of FamilyIds an instantiated Asset must include at "
            "least one of. MUST be non-empty."
        ),
    )
    cardinality: SlotCardinality = Field(
        ...,
        description=(
            "How many Assets can fill this slot at instantiation: "
            "Exactly1, ZeroOrOne, OneOrMore, ZeroOrMore."
        ),
    )
    default_settings: dict[str, Any] | None = Field(
        None,
        description=(
            "Optional template defaults applied at instantiation "
            "unless overridden by the instantiator."
        ),
    )
    default_placement: PlacementBody | None = Field(
        None,
        description="Optional template-default placement for the slot.",
    )

    def to_domain(self) -> TemplateSlot:
        """Convert this wire body to the domain TemplateSlot VO."""
        return TemplateSlot(
            slot_name=SlotName(self.slot_name),
            required_family_ids=self.required_family_ids,
            cardinality=self.cardinality,
            default_settings=self.default_settings,
            default_placement=(
                self.default_placement.to_domain() if self.default_placement is not None else None
            ),
        )


__all__ = ["TemplateSlotBody"]
