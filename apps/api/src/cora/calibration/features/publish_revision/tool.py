"""MCP tool for the `publish_revision` slice.

Mirrors the REST route shape: publishes a named revision of an
existing Calibration to a peer facility under an Active outbound
Permit. Returns the receipt_id for audit anchoring.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.calibration.features.publish_revision.command import (
    PublishCalibrationRevision,
)
from cora.calibration.features.publish_revision.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class PublishCalibrationRevisionOutput(BaseModel):
    """Structured output of the `publish_revision` MCP tool."""

    receipt_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `publish_revision` tool on the given MCP server."""

    @mcp.tool(
        name="publish_revision",
        description=(
            "Publish an existing Calibration revision to a peer facility "
            "under an Active outbound Permit. Resolves the Permit via "
            "PermitLookup keyed on (peer_facility_id, CalibrationRevision); "
            "raises if no Active permit authorizes the publish. The "
            "handler canonicalizes the artifact, signs via SignaturePort, "
            "publishes via PublishPort, then atomically appends "
            "CalibrationRevisionPublished + PublicationReceiptRecorded "
            "across the Calibration and Permit streams."
        ),
    )
    async def publish_revision_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        calibration_id: Annotated[UUID, Field(description="Target calibration's id.")],
        revision_id: Annotated[
            UUID,
            Field(description="Revision on the calibration to publish."),
        ],
        peer_facility_id: Annotated[
            str,
            Field(description="Opaque peer-facility id; matched to the outbound Permit."),
        ],
        idempotency_key: Annotated[
            str | None,
            Field(default=None, description="Optional Idempotency-Key per logical request."),
        ] = None,
    ) -> PublishCalibrationRevisionOutput:
        handler = get_handler()
        receipt_id = await handler(
            PublishCalibrationRevision(
                calibration_id=calibration_id,
                revision_id=revision_id,
                peer_facility_id=peer_facility_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
            idempotency_key=idempotency_key,
        )
        return PublishCalibrationRevisionOutput(receipt_id=receipt_id)
