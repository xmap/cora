"""MCP tool for the `get_model` query slice.

Surfaces the same handler the REST route uses. Returns a structured
GetModelOutput on hit. On miss raises an exception that FastMCP
wraps as `isError: true` with a text diagnostic, matching the REST
404 behaviour in MCP's error idiom (LLM consumers get a clear
"model not found" message rather than null structuredContent they
have to interpret).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
)
from cora.equipment.features.get_model.handler import Handler
from cora.equipment.features.get_model.query import GetModel
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ManufacturerOutput(BaseModel):
    """Structured output for a model's manufacturer.

    `name` is required; `identifier` and `identifier_type` are both
    set or both null (pairing invariant enforced by the domain VO).
    `identifier_type` is the closed-StrEnum scheme string value
    (ROR / GRID / ISNI) when present.
    """

    name: str = Field(..., max_length=MANUFACTURER_NAME_MAX_LENGTH)
    identifier: str | None = Field(default=None, max_length=MANUFACTURER_IDENTIFIER_MAX_LENGTH)
    identifier_type: str | None = None


class GetModelOutput(BaseModel):
    """Structured output of the `get_model` MCP tool.

    Mirrors the REST `ModelResponse` shape: `model_id`, `name`,
    nested `manufacturer`, `part_number`, sorted `declared_families`
    list, `status` enum string, and optional `version_tag`.
    """

    model_id: UUID
    name: str = Field(..., max_length=MODEL_NAME_MAX_LENGTH)
    manufacturer: ManufacturerOutput
    part_number: str = Field(..., max_length=MODEL_PART_NUMBER_MAX_LENGTH)
    declared_families: list[UUID]
    status: str
    version_tag: str | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_model` tool on the given MCP server."""

    @mcp.tool(
        name="get_model",
        description="Fetch a vendor-catalog Model by id.",
    )
    async def get_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        model_id: Annotated[
            UUID,
            Field(description="Target model's id."),
        ],
    ) -> GetModelOutput:
        handler = get_handler()
        model = await handler(
            GetModel(model_id=model_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if model is None:
            msg = f"Model {model_id} not found"
            raise ValueError(msg)
        manufacturer = model.manufacturer
        return GetModelOutput(
            model_id=model.id,
            name=model.name.value,
            manufacturer=ManufacturerOutput(
                name=manufacturer.name.value,
                identifier=(
                    manufacturer.identifier.value if manufacturer.identifier is not None else None
                ),
                identifier_type=(
                    manufacturer.identifier_type.value
                    if manufacturer.identifier_type is not None
                    else None
                ),
            ),
            part_number=model.part_number.value,
            declared_families=sorted(model.declared_families, key=str),
            status=model.status.value,
            version_tag=model.version,
        )
