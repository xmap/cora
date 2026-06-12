"""Shared Pydantic wire-format mirror of the `TemplateWire` value object.

`TemplateWire` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates.assembly.state`). The 4-tuple
`(source_slot_name, source_port_name, target_slot_name,
target_port_name)` IS the identity; the frozenset deduplicates on
the tuple.

Pydantic enforces field length at the API boundary; the degenerate
full-self-loop case (same slot AND same port on both endpoints)
surfaces from `TemplateWire.__post_init__` as
`InvalidWireSpecError` -> HTTP 400.
"""

from pydantic import BaseModel, Field

from cora.equipment.aggregates.assembly.state import (
    WIRE_PORT_NAME_MAX_LENGTH,
    TemplateWire,
)


class TemplateWireBody(BaseModel):
    """Wire format for a TemplateWire value object."""

    source_slot_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
    )
    source_port_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
    )
    target_slot_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
    )
    target_port_name: str = Field(
        ...,
        min_length=1,
        max_length=WIRE_PORT_NAME_MAX_LENGTH,
    )

    def to_domain(self) -> TemplateWire:
        """Convert this wire body to the domain TemplateWire VO."""
        return TemplateWire(
            source_slot_name=self.source_slot_name,
            source_port_name=self.source_port_name,
            target_slot_name=self.target_slot_name,
            target_port_name=self.target_port_name,
        )


__all__ = ["TemplateWireBody"]
