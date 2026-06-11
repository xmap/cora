"""MCP tool for the `list_clearances` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance import ClearanceStatus
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
)
from cora.safety.features.list_clearances.handler import Handler
from cora.safety.features.list_clearances.query import (
    ClearanceStatusFilter,
    ListClearances,
    RiskBandFilter,
)


class BindingsByKindOutput(BaseModel):
    """Per-kind binding-id arrays surfaced on the list MCP tool output.

    Mirrors `cora.safety.features.list_clearances.route.BindingsByKind`
    shape exactly (4 named `<kind>_ids` fields aligned with the
    projection's plural column names, no `additionalProperties`).
    ExternalRefBinding refs are NOT surfaced (anti-corruption refs, not
    projected; see tool description).
    """

    subject_ids: list[UUID] = Field(default_factory=list[UUID])
    asset_ids: list[UUID] = Field(default_factory=list[UUID])
    run_ids: list[UUID] = Field(default_factory=list[UUID])
    procedure_ids: list[UUID] = Field(default_factory=list[UUID])


class ClearanceSummaryItemOutput(BaseModel):
    clearance_id: UUID
    template_id: UUID
    template_code: str
    facility_code: str
    title: str = Field(..., max_length=CLEARANCE_TITLE_MAX_LENGTH)
    external_id: str | None = Field(default=None, max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH)
    status: ClearanceStatus
    risk_band: RiskBand | None = None
    bindings: BindingsByKindOutput
    parent_id: UUID | None = None
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = None
    last_reviewed_by: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_due_at: datetime | None = None


class ListClearancesOutput(BaseModel):
    """Structured output of the `list_clearances` MCP tool."""

    items: list[ClearanceSummaryItemOutput]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_clearances` tool on the given MCP server."""

    @mcp.tool(
        name="list_clearances",
        description=(
            "List clearances with cursor pagination + 9 optional filters. "
            "Filters: template_id / template_code / status / risk_band / "
            "facility_code + 4 "
            "binding-id filters (binds_to_subject_id / binds_to_asset_id / "
            "binds_to_run_id / binds_to_procedure_id). Returns sorted by "
            "registered_at ASC. ExternalRefBinding refs (for example, proposal / btr / "
            "lab_visit / session) are NOT filterable here; the review_steps "
            "chain is NOT in the response. Fetch get_clearance for both."
        ),
    )
    async def list_clearances_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None, Field(default=None, description="Opaque pagination cursor.")
        ] = None,
        limit: Annotated[
            int, Field(default=50, ge=1, le=100, description="Page size (1-100).")
        ] = 50,
        template_id: Annotated[
            UUID | None,
            Field(default=None, description="Template-id filter (exact match)."),
        ] = None,
        template_code: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=50,
                description="Template-code filter (exact match).",
            ),
        ] = None,
        status: Annotated[
            ClearanceStatusFilter | None, Field(default=None, description="Status filter.")
        ] = None,
        risk_band: Annotated[
            RiskBandFilter | None, Field(default=None, description="Risk-band filter.")
        ] = None,
        facility_code: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=32,
                pattern=r"^[a-z0-9-]{1,32}$",
                description="Facility filter (cross-deployment slug).",
            ),
        ] = None,
        binds_to_subject_id: Annotated[
            UUID | None, Field(default=None, description="Subject-binding filter.")
        ] = None,
        binds_to_asset_id: Annotated[
            UUID | None, Field(default=None, description="Asset-binding filter.")
        ] = None,
        binds_to_run_id: Annotated[
            UUID | None, Field(default=None, description="Run-binding filter.")
        ] = None,
        binds_to_procedure_id: Annotated[
            UUID | None, Field(default=None, description="Procedure-binding filter.")
        ] = None,
    ) -> ListClearancesOutput:
        handler = get_handler()
        page = await handler(
            ListClearances(
                cursor=cursor,
                limit=limit,
                template_id=template_id,
                template_code=template_code,
                status=status,
                risk_band=risk_band,
                facility_code=facility_code,
                binds_to_subject_id=binds_to_subject_id,
                binds_to_asset_id=binds_to_asset_id,
                binds_to_run_id=binds_to_run_id,
                binds_to_procedure_id=binds_to_procedure_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ListClearancesOutput(
            items=[
                ClearanceSummaryItemOutput(
                    clearance_id=item.clearance_id,
                    template_id=item.template_id,
                    template_code=item.template_code,
                    facility_code=item.facility_code,
                    title=item.title,
                    external_id=item.external_id,
                    status=ClearanceStatus(item.status),
                    risk_band=RiskBand(item.risk_band) if item.risk_band is not None else None,
                    bindings=BindingsByKindOutput(
                        subject_ids=item.subject_binding_ids,
                        asset_ids=item.asset_binding_ids,
                        run_ids=item.run_binding_ids,
                        procedure_ids=item.procedure_binding_ids,
                    ),
                    parent_id=item.parent_id,
                    registered_at=item.registered_at,
                    last_status_changed_at=item.last_status_changed_at,
                    last_status_reason=item.last_status_reason,
                    last_reviewed_by=item.last_reviewed_by,
                    valid_from=item.valid_from,
                    valid_until=item.valid_until,
                    next_review_due_at=item.next_review_due_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
