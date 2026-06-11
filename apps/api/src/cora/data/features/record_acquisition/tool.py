"""MCP tool for the `record_acquisition` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. The body shape mirrors the REST request: the
three cross-aggregate bindings, the instrument wall-clock captured_at,
and the two carrier dicts. `acquisition_id` is minted by the handler;
`occurred_at` is stamped from the Clock port.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.features.record_acquisition.command import RecordAcquisition
from cora.data.features.record_acquisition.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RecordAcquisitionOutput(BaseModel):
    """Structured output of the `record_acquisition` MCP tool."""

    acquisition_id: UUID = Field(description="Identifier of the newly recorded Acquisition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `record_acquisition` tool on the given MCP server."""

    @mcp.tool(
        name="record_acquisition",
        description=(
            "Record a new Acquisition: the birth-certificate fact that a "
            "producing Asset captured bytes into a Dataset under an optional "
            "Run context. The producing Asset's Family must declare the "
            "Capturing affordance. captured_at is the instrument wall-clock "
            "(may precede the recording time). producing_run_id is optional "
            "(omit for calibration / dark-field / standalone captures)."
        ),
    )
    async def record_acquisition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        dataset_id: Annotated[
            UUID,
            Field(description="Id of the logical Dataset this capture produced."),
        ],
        producing_asset_id: Annotated[
            UUID,
            Field(
                description=(
                    "Id of the capturing Asset. Its Family must declare the Capturing affordance."
                )
            ),
        ],
        captured_at: Annotated[
            datetime,
            Field(
                description=(
                    "Instrument wall-clock moment the bytes were physically "
                    "produced. May precede the recording time (backfills)."
                )
            ),
        ],
        producing_run_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional id of the Run context. Omit or null for "
                    "calibration / dark-field / standalone captures."
                ),
            ),
        ] = None,
        settings: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Operator / system settings active at capture. Shape-only "
                    "validated today (primitive leaves). Defaults to empty."
                ),
            ),
        ] = None,
        evidence: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Capture-specific evidence (freeform placeholder). Shape-"
                    "only validated today. Defaults to empty."
                ),
            ),
        ] = None,
    ) -> RecordAcquisitionOutput:
        handler = get_handler()
        acquisition_id = await handler(
            RecordAcquisition(
                dataset_id=dataset_id,
                producing_asset_id=producing_asset_id,
                captured_at=captured_at,
                producing_run_id=producing_run_id,
                settings=settings or {},
                evidence=evidence or {},
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RecordAcquisitionOutput(acquisition_id=acquisition_id)
