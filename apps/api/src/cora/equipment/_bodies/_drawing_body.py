"""Shared Pydantic wire-format mirror of the `Drawing` value object.

Hoisted from `register_mount.route` at the third importer
(register_mount + register_asset), satisfying the rule-of-three
precedent that landed `_placement_body` and `make_asset_update_handler`.

`Drawing` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates._drawing`); this body is purely the
wire shape that Pydantic parses, with one `to_domain()` method that
constructs the domain VO (and may raise `InvalidDrawingError` on
domain-rule violations like empty number, mapped to 400 by the BC's
exception handler).
"""

from pydantic import BaseModel, Field

from cora.equipment.aggregates._drawing import (
    DRAWING_NUMBER_MAX_LENGTH,
    DRAWING_REVISION_MAX_LENGTH,
    Drawing,
    DrawingSystem,
)


class DrawingBody(BaseModel):
    """Wire format for a `Drawing` value object."""

    system: DrawingSystem = Field(
        ...,
        description="The external document-management system (ICMS / EDMS / DOI).",
    )
    number: str = Field(
        ...,
        min_length=1,
        max_length=DRAWING_NUMBER_MAX_LENGTH,
        description="Document identifier within the system.",
    )
    revision: str | None = Field(
        None,
        max_length=DRAWING_REVISION_MAX_LENGTH,
        description=(
            "Optional revision pin; None means 'resolves to latest' "
            "(ISO 7200 / DOI / EDMS default-resolution semantics)."
        ),
    )

    def to_domain(self) -> Drawing:
        return Drawing(system=self.system, number=self.number, revision=self.revision)
