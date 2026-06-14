"""Shared Pydantic wire-format mirror of the `SubAssemblyLink` value object.

`SubAssemblyLink` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates.assembly.state`): a version-pinned link
from a parent Assembly to a child Assembly. It occupies a named
position (`slot_name`, sharing the slot-name namespace with
`required_slots`) and pins the child's `content_hash` at authoring
time (snapshot semantics).

Pydantic enforces field shape at the API boundary. Domain invariants
surface at `to_domain()` time: a blank `content_hash` raises
`InvalidSubAssemblyLinkError` and an over-long / blank `slot_name`
raises `InvalidSlotNameError` (both HTTP 400). Existence of the
referenced child Assembly and the content_hash pin are checked
cross-aggregate in the define / version handler + decider.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from cora.equipment.aggregates.assembly.state import (
    SLOT_NAME_MAX_LENGTH,
    SlotName,
    SubAssemblyLink,
)


class SubAssemblyLinkBody(BaseModel):
    """Wire format for a SubAssemblyLink value object."""

    slot_name: str = Field(
        ...,
        min_length=1,
        max_length=SLOT_NAME_MAX_LENGTH,
        description=(
            "Named position this sub-assembly occupies in the parent "
            "(e.g., 'optics'). Shares the slot-name namespace with "
            "required_slots; must not collide with a leaf slot or "
            "another link."
        ),
    )
    sub_assembly_id: UUID = Field(
        ...,
        description="Id of the child Assembly included at this position.",
    )
    content_hash: str = Field(
        ...,
        min_length=1,
        description=(
            "The child Assembly's content_hash, pinned at authoring "
            "time (snapshot). A later child re-version does not change "
            "the parent's identity until the parent is re-defined or "
            "re-versioned to adopt it."
        ),
    )

    def to_domain(self) -> SubAssemblyLink:
        """Convert this wire body to the domain SubAssemblyLink VO."""
        return SubAssemblyLink(
            slot_name=SlotName(self.slot_name),
            sub_assembly_id=self.sub_assembly_id,
            content_hash=self.content_hash,
        )


__all__ = ["SubAssemblyLinkBody"]
