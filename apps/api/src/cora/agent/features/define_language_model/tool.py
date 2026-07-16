"""MCP tool for the `define_language_model` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
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
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DefineLanguageModelOutput(BaseModel):
    """Structured output of the `define_language_model` MCP tool."""

    language_model_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_language_model` tool on the given MCP server."""

    @mcp.tool(
        name="define_language_model",
        description=(
            "Define a new LanguageModel catalog entry (lands in Defined; a "
            "separate approval promotes it to usable). Required: name, "
            "provider, model, served_via, cost_basis, data_tier, "
            "archivability. Optional: language_model_id (omit to mint "
            "server-side), snapshot_pin, endpoint_note."
        ),
    )
    async def define_language_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=LANGUAGE_MODEL_NAME_MAX_LENGTH,
                description="Display name.",
            ),
        ],
        provider: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_REF_PROVIDER_MAX_LENGTH,
                description="LLM provider name.",
            ),
        ],
        model: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_REF_MODEL_MAX_LENGTH,
                description="Provider-specific model identifier.",
            ),
        ],
        served_via: Annotated[
            ServingRoute,
            Field(description="Serving route: Direct, Argo, or InHouse."),
        ],
        cost_basis: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Discriminated cost-basis payload: kind=TokenPricing with "
                    "the four per-million-token USD rates, or "
                    "kind=GpuHourPricing with usd_per_gpu_hour."
                ),
            ),
        ],
        data_tier: Annotated[
            DataSensitivityTier,
            Field(description="Data class allowed to reach this model: Open, Internal, Sensitive."),
        ],
        archivability: Annotated[
            ArchivabilityTier,
            Field(description="Reproducibility axis: Pinned or Alias."),
        ],
        language_model_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional caller-supplied id for configuration-seeded "
                    "catalogs. Null mints a server-side UUIDv7."
                ),
            ),
        ] = None,
        snapshot_pin: Annotated[
            str | None,
            Field(
                default=None,
                max_length=MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
                description="Optional snapshot pin.",
            ),
        ] = None,
        endpoint_note: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=ENDPOINT_NOTE_MAX_LENGTH,
                description="Optional serving detail (pool name, broker route).",
            ),
        ] = None,
    ) -> DefineLanguageModelOutput:
        handler = get_handler()
        new_id = await handler(
            DefineLanguageModel(
                name=name,
                provider=provider,
                model=model,
                served_via=served_via.value,
                cost_basis=cost_basis,
                data_tier=data_tier.value,
                archivability=archivability.value,
                language_model_id=language_model_id,
                snapshot_pin=snapshot_pin,
                endpoint_note=endpoint_note,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineLanguageModelOutput(language_model_id=new_id)
