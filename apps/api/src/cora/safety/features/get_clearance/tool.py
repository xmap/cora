"""MCP tool for the `get_clearance` query slice.

Surfaces the same handler the REST route uses, exposed as an MCP tool.
On miss raises `ValueError` so FastMCP wraps the response as
`isError: true` with a clear diagnostic.

Same response shape as the REST route: polymorphic `bindings`,
`declarations`, `review_steps` carry JSON dicts whose `kind` discriminator
selects the variant shape.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    Clearance,
    ClearanceStatus,
    ReviewStep,
)
from cora.safety.aggregates.clearance.events import (
    serialize_binding,
    serialize_declaration,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.features.get_clearance.handler import Handler
from cora.safety.features.get_clearance.query import GetClearance


class ReviewStepOutput(BaseModel):
    step_index: int
    role: str
    decided_by: UUID
    decision: str
    decided_at: datetime
    notes: str | None = None


class ClearanceOutput(BaseModel):
    """Structured output of the `get_clearance` MCP tool (on hit)."""

    id: UUID
    template_id: UUID
    facility_code: str
    title: str = Field(..., max_length=CLEARANCE_TITLE_MAX_LENGTH)
    bindings: list[dict[str, Any]]
    declarations: list[dict[str, Any]]
    risk_band: RiskBand | None = None
    review_steps: list[ReviewStepOutput]
    status: ClearanceStatus
    external_id: str | None = Field(default=None, max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH)
    parent_id: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_due_at: datetime | None = None


def _review_step_to_output(step: ReviewStep) -> ReviewStepOutput:
    return ReviewStepOutput(
        step_index=step.step_index,
        role=step.role,
        decided_by=step.decided_by,
        decision=step.decision,
        decided_at=step.decided_at,
        notes=step.notes,
    )


def _clearance_to_output(clearance: Clearance) -> ClearanceOutput:
    return ClearanceOutput(
        id=clearance.id,
        template_id=clearance.template_id,
        facility_code=clearance.facility_code.value,
        title=clearance.title.value,
        bindings=[serialize_binding(b) for b in clearance.bindings],
        declarations=[serialize_declaration(d) for d in clearance.declarations],
        risk_band=clearance.risk_band,
        review_steps=[_review_step_to_output(r) for r in clearance.review_steps],
        status=clearance.status,
        external_id=clearance.external_id,
        parent_id=clearance.parent_id,
        valid_from=clearance.valid_from,
        valid_until=clearance.valid_until,
        next_review_due_at=clearance.next_review_due_at,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="get_clearance",
        description=(
            "Look up a safety-form clearance by id. Returns template_id, title, "
            "bindings, declarations, risk_band, reviewer chain, current FSM "
            "status, and validity window. Polymorphic fields (bindings, "
            "declarations, review_steps) carry JSON objects with a `kind` "
            "discriminator."
        ),
    )
    async def get_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        clearance_id: Annotated[
            UUID,
            Field(description="Target clearance's id."),
        ],
    ) -> ClearanceOutput:
        handler = get_handler()
        clearance = await handler(
            GetClearance(clearance_id=clearance_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if clearance is None:
            msg = f"Clearance {clearance_id} not found"
            raise ValueError(msg)
        return _clearance_to_output(clearance)
