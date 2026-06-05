"""Shared Pydantic wire-format for the `assign_fixture_persistent_id` slice.

Mirrors `_asset_persistent_identifier_body` at the BC root. Per Section
6.5 of [[project-fixture-pidinst-design]], slice F at the Fixture tier
does NOT carry a domain-VO wire mirror (the `PersistentIdentifier` VO
is never parsed at the wire; it is server-minted inside the handler).
This module instead carries the request + response wire surface for the
single POST endpoint:

  - `AssignFixturePersistentIdRequest`: `(scheme, suffix | None)`
    operator intent. The handler resolves the suffix into a full
    `PersistentIdentifier` via the configured `DoiMinter` port.
  - `AssignFixturePersistentIdResponse`: `(scheme, value)` echoed back
    so the operator learns the server-minted identifier without a
    follow-up GET (Section 6.5 deviation from the empty-201 convention
    for Fixture mutations).

Reuses `PersistentIdentifierScheme` + `PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH`
from the Asset module per Locks 2-4 of the design memo (the VO + enum
ship at the Asset tier and the Fixture tier imports them unchanged).
"""

from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import (
    PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
    PersistentIdentifierScheme,
)


class AssignFixturePersistentIdRequest(BaseModel):
    """Body for `POST /fixtures/{fixture_id}/assign-persistent-identifier`.

    `scheme` selects the PID scheme; v1 supports DOI and HANDLE.
    `suffix` is the optional operator-supplied local part; when absent
    the configured `DoiMinter` adapter auto-generates one. No `value`
    field per the server-mint posture.
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
            "configured DoiMinter adapter auto-generates the suffix."
        ),
    )


class AssignFixturePersistentIdResponse(BaseModel):
    """Response body for `POST /fixtures/{fixture_id}/assign-persistent-identifier`.

    Echoes the server-minted `(scheme, value)` pair so the operator
    learns the assigned identifier without a follow-up GET. Mirrors the
    Asset-tier sibling exactly; the value is server-minted and not
    derivable from the request alone.
    """

    scheme: str = Field(
        ...,
        description="Assigned PIDINST Property 1 scheme value (DOI or Handle).",
    )
    value: str = Field(
        ...,
        description="Authority-assigned persistent identifier string.",
    )
