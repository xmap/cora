"""HTTP route for the `define_language_model` slice.

`POST /language-models` with body carrying name / provider / model /
served_via / cost_basis / data_tier / archivability + optional
language_model_id / snapshot_pin / endpoint_note. Returns 201 +
`{language_model_id}` on success.

`served_via` / `data_tier` / `archivability` are typed as their
StrEnums so Pydantic rejects unknown values with 422 at the boundary
(the register_asset `tier` pattern). `cost_basis` stays a raw dict:
its discriminated shape is a domain concern the decider validates,
so a bad kind or a negative rate maps to 400 InvalidCostBasisError
rather than 422.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.agent.aggregates.agent import (
    MODEL_REF_MODEL_MAX_LENGTH,
    MODEL_REF_PROVIDER_MAX_LENGTH,
    MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
)
from cora.agent.aggregates.language_model import (
    ENDPOINT_NOTE_MAX_LENGTH,
    LANGUAGE_MODEL_NAME_MAX_LENGTH,
    ArchivabilityTier,
    DataSensitivityTier,
    ServingRoute,
)
from cora.agent.features.define_language_model.command import DefineLanguageModel
from cora.agent.features.define_language_model.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DefineLanguageModelRequest(BaseModel):
    """Body for `POST /language-models`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=LANGUAGE_MODEL_NAME_MAX_LENGTH,
        description="Human-readable display name for the catalog entry.",
    )
    provider: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_PROVIDER_MAX_LENGTH,
        description="LLM provider name (`anthropic`, `openai`, `google`, etc.).",
    )
    model: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_MODEL_MAX_LENGTH,
        description="Provider-specific model identifier (`claude-sonnet-4-6`, etc.).",
    )
    served_via: ServingRoute = Field(
        ...,
        description="Serving route. One of: Direct, Argo, InHouse.",
    )
    cost_basis: dict[str, Any] = Field(
        ...,
        description=(
            "Discriminated cost-basis payload. Either kind=TokenPricing with "
            "input_per_mtok / output_per_mtok / cache_write_per_mtok / "
            "cache_read_per_mtok, or kind=GpuHourPricing with usd_per_gpu_hour. "
            "All rates are finite non-negative USD."
        ),
    )
    data_tier: DataSensitivityTier = Field(
        ...,
        description=(
            "Which class of data may reach this model. One of: Open, Internal, Sensitive."
        ),
    )
    archivability: ArchivabilityTier = Field(
        ...,
        description="Reproducibility axis. One of: Pinned, Alias.",
    )
    language_model_id: UUID | None = Field(
        default=None,
        description=(
            "Optional caller-supplied id for configuration-seeded catalogs "
            "needing stable ids across environments. Omit (or pass null) to "
            "let the server mint a UUIDv7."
        ),
    )
    snapshot_pin: str | None = Field(
        default=None,
        max_length=MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
        description=(
            "Optional provider-specific snapshot identifier (Anthropic snapshot "
            "string, OpenAI fingerprint, etc.) for reproducibility. Pass null "
            "to leave unpinned."
        ),
    )
    endpoint_note: str | None = Field(
        default=None,
        min_length=1,
        max_length=ENDPOINT_NOTE_MAX_LENGTH,
        description=(
            "Optional serving detail (pool name, broker route). A note, not an "
            "address: connection configuration lives with the serving layer."
        ),
    )


class DefineLanguageModelResponse(BaseModel):
    """Response body for `POST /language-models`."""

    language_model_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.agent.define_language_model
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/language-models",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineLanguageModelResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only name, invalid "
                "provider / model / snapshot_pin, empty endpoint note, or "
                "malformed cost_basis: unknown kind, missing rate, negative "
                "or non-finite rate)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The target LanguageModel stream already has events. Reachable "
                "in practice only with a caller-supplied language_model_id; "
                "essentially impossible for server-minted UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, length "
                "out of bounds, unknown served_via / data_tier / archivability "
                "value, invalid UUID), OR Idempotency-Key was reused with a "
                "different request body."
            ),
        },
    },
    summary="Define a new LanguageModel catalog entry (lands in Defined)",
)
async def post_language_models(
    body: DefineLanguageModelRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DefineLanguageModelResponse:
    language_model_id = await handler(
        DefineLanguageModel(
            name=body.name,
            provider=body.provider,
            model=body.model,
            served_via=body.served_via.value,
            cost_basis=body.cost_basis,
            data_tier=body.data_tier.value,
            archivability=body.archivability.value,
            language_model_id=body.language_model_id,
            snapshot_pin=body.snapshot_pin,
            endpoint_note=body.endpoint_note,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineLanguageModelResponse(language_model_id=language_model_id)
