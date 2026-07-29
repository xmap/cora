"""MCP tool for the `ingest_scan` slice.

Surfaces the same handler the REST route uses. The body mirrors the
REST request: only what the caller knows that the file cannot say.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.features.ingest_scan.command import IngestScan
from cora.data.features.ingest_scan.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class IngestScanOutput(BaseModel):
    """Structured output of the `ingest_scan` MCP tool."""

    dataset_id: UUID = Field(description="Identifier of the newly registered Dataset.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `ingest_scan` tool on the given MCP server."""

    @mcp.tool(
        name="ingest_scan",
        description=(
            "Ingest one finished scan file into the record: reads the file's "
            "facts (frame roles, counts, angles), digests its bytes, and "
            "registers Dataset + Distribution + Acquisition atomically. "
            "Refuses files that are unreadable, unrecognized, structurally "
            "incomplete, still changing, or already ingested (same checksum). "
            "captured_at is accepted only when the file carries no parseable "
            "timestamp of its own."
        ),
    )
    async def ingest_scan_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        locator: Annotated[
            str,
            Field(
                description=(
                    "URI of the scan file, interpreted by the deployment's "
                    "scan reader (file:// against the configured roots)."
                )
            ),
        ],
        producing_asset_id: Annotated[
            UUID,
            Field(
                description=(
                    "Id of the capturing Asset. Its Family must declare the Capturing affordance."
                )
            ),
        ],
        supply_id: Annotated[
            UUID,
            Field(description="Id of the Storage-kind Supply holding the file."),
        ],
        access_protocol: Annotated[
            str,
            Field(description="How a consumer reaches the bytes, for example 'POSIX'."),
        ],
        producing_run_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description="Optional id of the Run context.",
            ),
        ] = None,
        captured_at: Annotated[
            datetime | None,
            Field(
                default=None,
                description=(
                    "Operator-asserted acquisition time, accepted only when "
                    "the file has no parseable timestamp. Timezone-aware."
                ),
            ),
        ] = None,
    ) -> IngestScanOutput:
        handler = get_handler()
        dataset_id = await handler(
            IngestScan(
                locator=locator,
                producing_asset_id=producing_asset_id,
                supply_id=supply_id,
                access_protocol=access_protocol,
                producing_run_id=producing_run_id,
                captured_at=captured_at,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return IngestScanOutput(dataset_id=dataset_id)


__all__ = ["IngestScanOutput", "register"]
