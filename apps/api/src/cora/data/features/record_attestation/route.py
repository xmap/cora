"""HTTP route for the ``record_attestation`` slice.

``POST /attestations`` returns 201 + ``RecordAttestationResponse`` on
success. The body is slim: ``dataset_id`` (always), ``distribution_id``
(required for byte-level kinds), and ``kind``. CORA reads the
Distribution's bytes itself and computes the checksum, so the caller no
longer supplies an outcome or any evidence.

## Flat route

Per [[project_data_attestation_design]] L21: REST route is the flat
``/attestations`` (NOT nested under ``/datasets/{id}/`` because an
Attestation may span Dataset OR Dataset+Distribution).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.attestation import AttestationKind
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RecordAttestationRequest(BaseModel):
    """Body for ``POST /attestations``."""

    dataset_id: UUID = Field(
        ...,
        description="Identifier of the Dataset the Attestation is about (always required).",
    )
    distribution_id: UUID | None = Field(
        default=None,
        description=(
            "Identifier of the bound Distribution byte-copy whose bytes CORA "
            "will read and checksum. Required for byte-level kinds "
            "(ChecksumVerified today); null only for ConformsToValidated."
        ),
    )
    kind: AttestationKind = Field(
        ...,
        description=(
            "What property to attest. Closed enum; today only 'ChecksumVerified' is implemented."
        ),
    )

    model_config = {"extra": "forbid"}


class RecordAttestationResponse(BaseModel):
    """Response body for ``POST /attestations``."""

    attestation_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.record_attestation
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/attestations",
    status_code=status.HTTP_201_CREATED,
    response_model=RecordAttestationResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: kind not yet implemented in this "
                "release, or no checksum verifier is configured for the "
                "Distribution's URI scheme (e.g. globus://, or file:// with no "
                "posix_checksum_roots set)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate reference does not exist: dataset_id or "
                "distribution_id (when provided)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Dual-binding violation (kind requires/forbids "
                "distribution_id; Distribution's parent Dataset does not "
                "match) or strict-not-idempotent same-id re-issue."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Verify a Distribution and record an Attestation fact",
)
async def post_attestations(
    body: RecordAttestationRequest,
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
                "response instead of re-recording the Attestation."
            ),
        ),
    ] = None,
) -> RecordAttestationResponse:
    attestation_id = await handler(
        RecordAttestation(
            dataset_id=body.dataset_id,
            distribution_id=body.distribution_id,
            kind=body.kind.value,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RecordAttestationResponse(attestation_id=attestation_id)
