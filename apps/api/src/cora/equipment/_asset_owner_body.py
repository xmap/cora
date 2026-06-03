"""Shared Pydantic wire-format mirror of the `AssetOwner` VO.

Hoisted at the first importer (`register_asset`); the two mutation
slices `add_asset_owner` and `remove_asset_owner` reuse this mirror,
matching the precedent set by `_drawing_body` (Drawing),
`_placement_body` (Placement), and `_alternate_identifier_body`
(AlternateIdentifier).

`AssetOwner` is a frozen dataclass at the domain layer
(`cora.equipment.aggregates.asset.state.AssetOwner`); this body is
purely the wire shape Pydantic parses, with a `to_domain()` method
that constructs the domain VO. Optional fields default to None at
the wire; the pairing invariant (identifier <-> identifier_type)
is enforced in `AssetOwner.__post_init__` and surfaces as
`InvalidAssetOwnerIdentifierPairingError` (mapped to HTTP 400 by
the BC's exception handler).
"""

from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_CONTACT_MAX_LENGTH,
    ASSET_OWNER_IDENTIFIER_MAX_LENGTH,
    ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH,
    ASSET_OWNER_NAME_MAX_LENGTH,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)


class AssetOwnerBody(BaseModel):
    """Wire format for an `AssetOwner` value object (PIDINST v1.0 Property 5)."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ASSET_OWNER_NAME_MAX_LENGTH,
        description=(
            "Mandatory institutional owner name (PIDINST v1.0 Property "
            "5.1). Trimmed at the domain boundary. Unique within a "
            "single Asset's owners set."
        ),
    )
    contact: str | None = Field(
        None,
        min_length=1,
        max_length=ASSET_OWNER_CONTACT_MAX_LENGTH,
        description=(
            "Optional contact string for the owner (PIDINST 5.2). The "
            "spec hints at email; CORA accepts arbitrary free text "
            "(phone numbers, contact-form URLs, mail-team aliases all "
            "appear in DataCite corpora). Email-format validation is "
            "not enforced here."
        ),
    )
    identifier: str | None = Field(
        None,
        min_length=1,
        max_length=ASSET_OWNER_IDENTIFIER_MAX_LENGTH,
        description=(
            "Optional opaque owner identifier (PIDINST 5.3). The spec "
            "recommends a globally unique identifier; ROR is the "
            "preferred scheme. Both bare codes and full URLs are "
            "accepted; no normalization. Paired with identifier_type: "
            "both must be set or both must be absent."
        ),
    )
    identifier_type: str | None = Field(
        None,
        min_length=1,
        max_length=ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH,
        description=(
            "Optional scheme label for `identifier` (PIDINST 5.3.1). "
            "Free text by spec design (unlike sibling identifier-type "
            "fields): the field accepts ROR, GRID, ISNI, RAID, IGSN, "
            "internal facility codes, or any other authority. CORA "
            "does NOT case-normalize the recorded value. Paired with "
            "identifier."
        ),
    )

    def to_domain(self) -> AssetOwner:
        return AssetOwner(
            name=AssetOwnerName(self.name),
            contact=AssetOwnerContact(self.contact) if self.contact is not None else None,
            identifier=(
                AssetOwnerIdentifier(self.identifier) if self.identifier is not None else None
            ),
            identifier_type=(
                AssetOwnerIdentifierType(self.identifier_type)
                if self.identifier_type is not None
                else None
            ),
        )
