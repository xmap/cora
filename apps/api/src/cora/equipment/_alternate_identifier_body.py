"""Shared Pydantic wire-format mirror of the `AlternateIdentifier` VO.

Hoisted at the first importer (`register_asset`); the two future
mutation slices `add_asset_alternate_identifier` and
`remove_asset_alternate_identifier` reuse this mirror once they
land, matching the precedent set by `_drawing_body` (Drawing) and
`_placement_body` (Placement).

`AlternateIdentifier` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates.asset.state.AlternateIdentifier`);
this body is purely the wire shape that Pydantic parses, with a
single `to_domain()` method that constructs the domain VO and may
raise `InvalidAlternateIdentifierValueError` on domain-rule
violations (mapped to 400 by the BC's exception handler).
"""

from pydantic import BaseModel, Field

from cora.shared.identifier import (
    ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
    AlternateIdentifier,
    AlternateIdentifierKind,
)


class AlternateIdentifierBody(BaseModel):
    """Wire format for an `AlternateIdentifier` value object."""

    kind: AlternateIdentifierKind = Field(
        ...,
        description=(
            "Closed PIDINST v1.0 vocabulary: SerialNumber (manufacturer "
            "per-unit identifier), InventoryNumber (facility asset tag), "
            "or Other (vendor-specific or unconventional scheme)."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
        description=(
            "Operator-supplied opaque string identifying the Asset "
            "under the given scheme. Trimmed at the domain boundary."
        ),
    )

    def to_domain(self) -> AlternateIdentifier:
        return AlternateIdentifier(kind=self.kind, value=self.value)
