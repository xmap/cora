"""Shared Pydantic wire-format for the `assign_asset_persistent_id` slice.

Per Lock 22 of [[project-asset-persistent-id-write-design]], slice F
does NOT carry a domain-VO wire mirror (the `PersistentIdentifier` VO
is never parsed at the wire; it is server-minted inside the handler).
This module instead carries the request + response wire surface for
the single POST endpoint:

  - `AssignAssetPersistentIdRequest`: `(scheme, suffix | None)` operator
    intent. The handler resolves the suffix into a full
    `PersistentIdentifier` via the configured `PersistentIdentifierMinter` port.
  - `AssignAssetPersistentIdResponse`: `(scheme, value)` echoed back so the
    operator learns the server-minted identifier without a follow-up
    GET (Lock 17 deviation from the empty-201 convention).

Mirrors the placement of `_asset_owner_body` and
`_alternate_identifier_body` at the BC root.
"""

from pydantic import BaseModel, Field

from cora.shared.identifier import (
    PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
    PersistentIdentifierScheme,
)


class AssignAssetPersistentIdRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/assign-persistent-identifier`.

    `scheme` selects the PID scheme; v1 supports DOI and HANDLE.
    `suffix` is the optional operator-supplied local part; when absent
    the configured `PersistentIdentifierMinter` adapter auto-generates one. No `value`
    field per the server-mint posture (Lock 12).
    """

    scheme: PersistentIdentifierScheme = Field(
        ...,
        description="Closed PIDINST Property 1 scheme: DOI or HANDLE.",
    )
    suffix: str | None = Field(
        None,
        min_length=1,
        max_length=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
        description=(
            "Optional operator-supplied local part. When absent, the "
            "configured PersistentIdentifierMinter adapter auto-generates the suffix; "
            "the bare-request flow is the common case for retrospective "
            "bulk-mint per F1.4."
        ),
    )


class AssignAssetPersistentIdResponse(BaseModel):
    """Response body for `POST /assets/{asset_id}/assign-persistent-identifier`.

    Echoes the server-minted `(scheme, value)` pair so the operator
    learns the assigned identifier without a follow-up GET. Per Lock
    17, this is the only Asset POST that returns a structured body;
    the deviation is justified because the value is server-minted and
    not derivable from the request alone.
    """

    scheme: str = Field(
        ...,
        description="Assigned PIDINST Property 1 scheme value (DOI or Handle).",
    )
    value: str = Field(
        ...,
        description="Authority-assigned persistent identifier string.",
    )
