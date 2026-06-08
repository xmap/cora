"""HTTP route for the `register_facility` slice.

`POST /federation/facilities` with body carrying code + display_name +
kind + optional parent_id + optional alternate_identifiers. Returns
201 + `{facility_id, code}` on success.

The response echoes both the internal-opaque `facility_id` (UUID for
spine references within this deployment) AND the cross-deployment
convergent `code` per the two-tier identity contract; clients SHOULD
prefer `code` for any cross-BC or cross-deployment reference per
[[project_facility_aggregate_design]] L1.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates.facility import FacilityKind
from cora.federation.features.register_facility.command import RegisterFacility
from cora.federation.features.register_facility.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH
from cora.shared.identifier import (
    ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
    AlternateIdentifier,
    AlternateIdentifierKind,
)


class RegisterFacilityAlternateIdentifierBody(BaseModel):
    """Wire format for one `AlternateIdentifier` value object on the request body."""

    kind: AlternateIdentifierKind = Field(
        ...,
        description=(
            "Closed PIDINST v1.0 Property 13 vocabulary: SerialNumber "
            "(manufacturer per-unit identifier), InventoryNumber (facility "
            "asset tag), or Other (vendor-specific or unconventional scheme)."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
        description=(
            "Operator-supplied opaque string identifying the Facility "
            "under the given scheme. Trimmed at the domain boundary."
        ),
    )

    model_config = {"extra": "forbid"}

    def to_domain(self) -> AlternateIdentifier:
        return AlternateIdentifier(kind=self.kind, value=self.value)


class RegisterFacilityRequest(BaseModel):
    """Body for `POST /federation/facilities`."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=FACILITY_CODE_MAX_LENGTH,
        description=(
            "Cross-deployment convergent facility slug (lowercase ASCII "
            "alphanumeric and dash, 1-32 chars). Used to derive the "
            "deterministic Facility stream id; immutable post-genesis."
        ),
    )
    display_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Operator-supplied display string, trimmed and bounded "
            "1-200 chars at the domain boundary."
        ),
    )
    kind: FacilityKind = Field(
        ...,
        description=(
            "Closed enum: Site (ISA-95 Site; physical research facility) "
            "or Area (ISA-95 Area; experimental hall or building within a Site)."
        ),
    )
    parent_id: UUID | None = Field(
        default=None,
        description=(
            "Parent Facility id. MUST be omitted for kind=Site. MUST be "
            "provided for kind=Area. Cross-stream existence and "
            "parent-kind=Site validation are deferred to a future slice."
        ),
    )
    alternate_identifiers: list[RegisterFacilityAlternateIdentifierBody] = Field(
        default_factory=list[RegisterFacilityAlternateIdentifierBody],
        description=(
            "Optional day-one PIDINST alternate-identifier seed (Property 13). "
            "Defaults to empty. Add/remove slices are deferred."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterFacilityResponse(BaseModel):
    """Response body for `POST /federation/facilities`.

    Carries BOTH identity tiers per the two-tier identity contract:

      - `facility_id`: opaque UUID for spine references within this
        deployment.
      - `code`: cross-deployment convergent slug. Clients SHOULD prefer
        this for any cross-BC or cross-deployment reference.
    """

    facility_id: UUID
    code: str


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.federation.register_facility
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/facilities",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterFacilityResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "A Facility with the supplied code already exists. The "
                "deterministic stream-id derivation enforces code uniqueness "
                "at the live path; codes are immutable post-creation and "
                "may not be reused for a new facility after decommissioning."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid enum value, code violating the alphanumeric+dash "
                "pattern, display_name empty after trim, alternate_identifier "
                "kind out of closed enum, OR structural Facility invariant "
                "violated (Site has non-null parent_id, Area has null parent_id)), "
                "OR Idempotency-Key was reused with a different request body."
            ),
        },
    },
    summary="Register a new federation Facility (single-stream genesis)",
)
async def post_federation_facilities(
    body: RegisterFacilityRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of writing a duplicate Facility."
            ),
        ),
    ] = None,
) -> RegisterFacilityResponse:
    from cora.federation.aggregates._value_types import FacilityId

    facility_id = await handler(
        RegisterFacility(
            code=body.code,
            display_name=body.display_name,
            kind=body.kind,
            parent_id=FacilityId(body.parent_id) if body.parent_id is not None else None,
            alternate_identifiers=frozenset(alt.to_domain() for alt in body.alternate_identifiers),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterFacilityResponse(facility_id=facility_id, code=body.code)
