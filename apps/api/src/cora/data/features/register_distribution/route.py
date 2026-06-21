"""HTTP route for the `register_distribution` slice.

`POST /distributions` returns 201 + RegisterDistributionResponse on
success. Body carries the Distribution metadata: cross-aggregate
refs (dataset_id same-BC, supply_id cross-BC), addressing (uri +
access_protocol), and the byte-identical-copy invariants (checksum
+ byte_size + encoding).

## Flat route, nested checksum + encoding

Per [[project-data-distribution-design]] L21: REST route is the
flat `/distributions` (NOT nested under `/datasets/{id}/`). Body
shape uses nested `checksum` and `encoding` objects to mirror the
on-disk event payload (one less translation surface for typed
clients); the command object flattens them. Mirrors
`register_dataset` precedent.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
)
from cora.data.aggregates.distribution import (
    DISTRIBUTION_URI_MAX_LENGTH,
    AccessProtocol,
)
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DistributionChecksumRequest(BaseModel):
    """Bulk-content integrity hash on the registration request body."""

    algorithm: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Checksum algorithm name: 'sha256' for a single file or "
            "'sha256-tree' for a directory of files. Must equal the parent "
            "Dataset's algorithm (byte-identical-copy invariant)."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
        description="Canonical checksum value. For sha256: exactly 64 lowercase hex chars.",
    )


class DistributionEncodingRequest(BaseModel):
    """Structured encoding descriptor on the registration request body."""

    media_type: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_MEDIA_TYPE_MAX_LENGTH,
        description=(
            "Loose MIME-type-ish string describing the wire encoding "
            "(for example 'application/x-hdf5', 'application/x-zarr')."
        ),
    )
    conforms_to: list[str] = Field(
        default_factory=list[str],
        max_length=DATASET_CONFORMS_TO_MAX_ENTRIES,
        description=(
            "Profile URIs the Distribution claims to conform to "
            "(NeXus, OME-Zarr, CIF, etc.). Empty when no profile is claimed."
        ),
    )


class RegisterDistributionRequest(BaseModel):
    """Body for `POST /distributions`."""

    dataset_id: UUID = Field(
        ...,
        description=(
            "Identifier of the parent logical Dataset. Must resolve to a "
            "non-Discarded Dataset whose checksum + byte_size match the "
            "command's values (byte-identical-copy invariant)."
        ),
    )
    supply_id: UUID = Field(
        ...,
        description=(
            "Identifier of the storage-kind Supply hosting the bytes. Must "
            "resolve to a Supply with kind='Storage'; lifecycle status is "
            "not gated (Decommissioned Supplies accept new Distributions "
            "for archival completeness)."
        ),
    )
    uri: str = Field(
        ...,
        min_length=1,
        max_length=DISTRIBUTION_URI_MAX_LENGTH,
        description=(
            "Opaque URI string pointing at the bulk content "
            "(s3://, file://, https://, globus://, etc.)."
        ),
    )
    checksum: DistributionChecksumRequest = Field(
        ...,
        description="Bulk-content integrity hash (algorithm + value).",
    )
    byte_size: int = Field(
        ...,
        ge=0,
        description=(
            "Bulk content size in bytes. Zero is valid (empty Distribution "
            "of an empty Dataset). Must match the parent Dataset's byte_size."
        ),
    )
    encoding: DistributionEncodingRequest = Field(
        ...,
        description="Structured encoding descriptor (media_type + conforms_to profile URIs).",
    )
    access_protocol: AccessProtocol = Field(
        ...,
        description=(
            "Transport family of the URI. Closed enum: HTTPS, Globus, S3, "
            "POSIX, NFS, OAI_PMH. Widening is additive when a new "
            "transport adapter ships."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterDistributionResponse(BaseModel):
    """Response body for `POST /distributions`."""

    distribution_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.register_distribution
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/distributions",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterDistributionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: malformed URI, non-sha256 or "
                "malformed checksum, negative byte_size, invalid encoding "
                "media_type, or invalid conforms_to entry."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate reference does not exist: dataset_id "
                "(same-BC) or supply_id (cross-BC via SupplyLookup)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Registration-time conflict: Dataset is Discarded, Supply "
                "kind is not 'Storage', or checksum / byte_size do not "
                "match the parent Dataset (byte-identical-copy invariant)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new Distribution",
)
async def post_distributions(
    body: RegisterDistributionRequest,
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
                "response instead of re-creating the Distribution."
            ),
        ),
    ] = None,
) -> RegisterDistributionResponse:
    distribution_id = await handler(
        RegisterDistribution(
            dataset_id=body.dataset_id,
            supply_id=body.supply_id,
            uri=body.uri,
            checksum_algorithm=body.checksum.algorithm,
            checksum_value=body.checksum.value,
            byte_size=body.byte_size,
            media_type=body.encoding.media_type,
            conforms_to=frozenset(body.encoding.conforms_to),
            access_protocol=body.access_protocol.value,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterDistributionResponse(distribution_id=distribution_id)
