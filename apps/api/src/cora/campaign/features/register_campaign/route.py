"""HTTP route for the `register_campaign` slice.

Pydantic request/response schemas + APIRouter for `POST /campaigns`.
The slice's BC-level wiring (`cora.campaign.routes.register_campaign_routes`)
includes this router on the FastAPI app.

`external_refs` body shape:
`[{"scheme": "proposal", "value": "12345"}, ...]`; each item is
validated by the shared `Identifier` VO at command-build time.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.campaign.aggregates.campaign import (
    CAMPAIGN_DESCRIPTION_MAX_LENGTH,
    CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
    CAMPAIGN_NAME_MAX_LENGTH,
    CampaignIntent,
)
from cora.campaign.features.register_campaign.command import RegisterCampaign
from cora.campaign.features.register_campaign.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.identifier import (
    IDENTIFIER_SCHEME_MAX_LENGTH,
    IDENTIFIER_VALUE_MAX_LENGTH,
    Identifier,
)


class ExternalRefDTO(BaseModel):
    """Wire shape for an external-ref Identifier on the register_campaign request body."""

    scheme: str = Field(
        ...,
        min_length=1,
        max_length=IDENTIFIER_SCHEME_MAX_LENGTH,
        description=(
            "Scheme identifier for the upstream-deferred concept "
            "(for example 'proposal', 'btr', 'visit', 'cycle')."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=IDENTIFIER_VALUE_MAX_LENGTH,
        description="Facility-issued opaque value under the named scheme.",
    )


class RegisterCampaignRequest(BaseModel):
    """Body for `POST /campaigns`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=CAMPAIGN_NAME_MAX_LENGTH,
        description="Operator-meaningful Campaign name. Trimmed at the domain layer.",
    )
    intent: CampaignIntent = Field(
        ...,
        description=(
            "Closed intent-shape vocabulary: Series, Sweep, Coordination, "
            "Block. Describes what KIND of coordination the Campaign carries, "
            "not the scientific technique (technique tagging lives on tags)."
        ),
    )
    lead_actor_id: UUID = Field(
        ...,
        description=(
            "REQUIRED. The Campaign's PI / lead operator. Operator-asserted; "
            "may differ from the registering principal (LIMS Study Director "
            "precedent)."
        ),
    )
    subject_id: UUID | None = Field(
        default=None,
        description=(
            "Optional informational Subject reference. LOOSE policy: NOT "
            "enforced as a member-Run invariant. Multi-Subject Campaigns "
            "(Block, Sweep) are legitimate."
        ),
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=CAMPAIGN_DESCRIPTION_MAX_LENGTH,
        description="Optional free-form description. Trimmed at the domain layer.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "Optional free-form tags. Each tag 1-50 chars after trim. Empty list IS allowed."
        ),
    )
    external_refs: list[ExternalRefDTO] = Field(
        default_factory=list[ExternalRefDTO],
        description=(
            "Anti-corruption refs to upstream-deferred concepts (proposal, "
            "btr, visit, cycle). Empty list IS allowed."
        ),
    )
    external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
        description=(
            "Optional facility-minted or DataCite Project DOI assigned "
            "lazily. Today: operator-supplied at register time only; no "
            "mint slice yet."
        ),
    )


class RegisterCampaignResponse(BaseModel):
    """Response body for `POST /campaigns`."""

    campaign_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.campaign.register_campaign
    return handler


def _refs_from_dto(dto_refs: list[ExternalRefDTO]) -> frozenset[Identifier]:
    """Convert the body's list of DTOs to a typed frozenset of Identifier."""
    return frozenset(Identifier(scheme=r.scheme, value=r.value) for r in dto_refs)


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterCampaignResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only name / description "
                "/ tag / external_id, or out-of-bounds external_ref scheme/value)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target Campaign stream already has "
                "events. Essentially impossible in production with UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid enum, length out of bounds), OR Idempotency-Key was "
                "reused with a different request body."
            ),
        },
    },
    summary="Register a new Campaign (lands in Planned)",
)
async def post_campaigns(
    body: RegisterCampaignRequest,
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
                "response instead of re-creating the Campaign."
            ),
        ),
    ] = None,
) -> RegisterCampaignResponse:
    campaign_id = await handler(
        RegisterCampaign(
            name=body.name,
            intent=body.intent,
            lead_actor_id=body.lead_actor_id,
            subject_id=body.subject_id,
            description=body.description,
            tags=frozenset(body.tags),
            external_refs=_refs_from_dto(body.external_refs),
            external_id=body.external_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterCampaignResponse(campaign_id=campaign_id)
