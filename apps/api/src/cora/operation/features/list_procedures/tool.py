"""MCP tool for the `list_procedures` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    ProcedureStatus,
)
from cora.operation.features.list_procedures.handler import Handler
from cora.operation.features.list_procedures.query import (
    ListProcedures,
    ProcedureStatusFilter,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class _ProcedureSummaryItemDTO(BaseModel):
    """One procedure in a paginated list (MCP-tool DTO; mirrors HTTP shape)."""

    procedure_id: UUID
    name: str = Field(..., max_length=PROCEDURE_NAME_MAX_LENGTH)
    kind: str = Field(..., max_length=PROCEDURE_KIND_MAX_LENGTH)
    target_asset_ids: list[UUID]
    parent_run_id: UUID | None = None
    status: ProcedureStatus
    activity_logbook_id: UUID | None = None
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)
    interrupted_at: datetime | None = None


class _ListProceduresOutput(BaseModel):
    """MCP tool output: page of procedures plus cursor."""

    items: list[_ProcedureSummaryItemDTO]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_procedures` tool on the given MCP server."""

    @mcp.tool(
        name="list_procedures",
        description=(
            "List procedures with cursor pagination + optional filters "
            "(status, kind, parent_run_id, target_asset_id). Reads from "
            "the proj_operation_procedure_summary projection."
        ),
    )
    async def list_procedures_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous page."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size; capped at 100."),
        ] = 50,
        status: Annotated[
            ProcedureStatusFilter | None,
            Field(description="Optional status filter."),
        ] = None,
        kind: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=PROCEDURE_KIND_MAX_LENGTH,
                description="Optional kind filter (exact match).",
            ),
        ] = None,
        parent_run_id: Annotated[
            UUID | None,
            Field(description="Optional Phase-of-Run filter."),
        ] = None,
        target_asset_id: Annotated[
            UUID | None,
            Field(description="Optional target-Asset filter."),
        ] = None,
    ) -> _ListProceduresOutput:
        handler = get_handler()
        page = await handler(
            ListProcedures(
                cursor=cursor,
                limit=limit,
                status=status,
                kind=kind,
                parent_run_id=parent_run_id,
                target_asset_id=target_asset_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return _ListProceduresOutput(
            items=[
                _ProcedureSummaryItemDTO(
                    procedure_id=item.procedure_id,
                    name=item.name,
                    kind=item.kind,
                    target_asset_ids=item.target_asset_ids,
                    parent_run_id=item.parent_run_id,
                    status=ProcedureStatus(item.status),
                    activity_logbook_id=item.activity_logbook_id,
                    registered_at=item.registered_at,
                    last_status_changed_at=item.last_status_changed_at,
                    last_status_reason=item.last_status_reason,
                    interrupted_at=item.interrupted_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
