"""MCP tool for the `start_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.handler import IdempotentHandler


class StartRunOutput(BaseModel):
    """Structured output of the `start_run` MCP tool."""

    run_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `start_run` tool on the given MCP server."""

    @mcp.tool(
        name="start_run",
        description=(
            "Start a new Run executing a Plan against an (optional) "
            "Subject. Validates at start time that the Plan is not "
            "Deprecated, the Subject (if given) is in Mounted or "
            "Measured, no bound Asset is Decommissioned, and the bound "
            "Assets' current capabilities cover the Method's needs "
            "(re-validated against current Asset state, not just the "
            "Plan-bind snapshot). Subject is omitted for dark-field / "
            "flat-field calibration runs."
        ),
    )
    async def start_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=RUN_NAME_MAX_LENGTH,
                description="Display name for the new run.",
            ),
        ],
        plan_id: Annotated[
            UUID,
            Field(description="Plan id this Run executes."),
        ],
        subject_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Subject being measured. Omit (or null) for calibration / dark-field runs."
                ),
            ),
        ] = None,
        raid: Annotated[
            str | None,
            Field(
                default=None,
                max_length=2048,
                description=(
                    "Research Activity Identifier (ISO 23527) of the research "
                    "activity this Run belongs to. Optional; opaque string carried "
                    "verbatim. RAiD is project/activity scoped: share one RAiD "
                    "across the many Runs of an activity, do not mint one per Run "
                    "(the Run id is the per-run identity). Used at PROV-O / "
                    "DataCite export boundaries for cross-facility provenance."
                ),
            ),
        ] = None,
        override_parameters: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Operator-supplied overrides on top of "
                    "Plan.default_parameters (RFC 7396 merge). The "
                    "post-merge result is validated against the owning "
                    "Method's parameters_schema; STRICT when the Method "
                    "declares no schema (non-empty effective rejected; "
                    "declare an empty `{}` schema for parameter-less "
                    "Methods). Omit or null for an empty overrides dict. "
                    "Effective-parameters resolution."
                ),
            ),
        ] = None,
        trigger_source: Annotated[
            str | None,
            Field(
                default=None,
                max_length=500,
                description=(
                    "Free-form text capturing what initiated this Run "
                    "(operator-manual, scheduler id, prior-run id, "
                    "automation). Optional."
                ),
            ),
        ] = None,
        campaign_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional Campaign id this Run joins at start time. When "
                    "provided, the handler atomically writes RunStarted "
                    "(carrying campaign_id) on the Run stream AND "
                    "CampaignRunAdded on the Campaign stream. The Campaign "
                    "must be in Planned, Active, or Held."
                ),
            ),
        ] = None,
        decided_by_decision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional Decision id that justified starting this Run "
                    "(cross-Plan pivots like EnergyChange). Maps to "
                    "prov:wasInformedBy at the future PROV-O export "
                    "adapter. Not verified at the write path."
                ),
            ),
        ] = None,
        pinned_calibration_ids: Annotated[
            list[UUID] | None,
            Field(
                default=None,
                description=(
                    "Optional CalibrationRevision ids pinned at this Run's "
                    "start time (Calibration BC AsShot anchor). "
                    "IMMUTABLE on the aggregate after start. NOT verified "
                    "at the write path. Omit or null for an empty pin set."
                ),
            ),
        ] = None,
    ) -> StartRunOutput:
        handler = get_handler()
        run_id = await handler(
            StartRun(
                name=name,
                plan_id=plan_id,
                subject_id=subject_id,
                raid=raid,
                override_parameters=override_parameters if override_parameters else {},
                trigger_source=trigger_source,
                campaign_id=campaign_id,
                decided_by_decision_id=decided_by_decision_id,
                pinned_calibration_ids=frozenset(pinned_calibration_ids)
                if pinned_calibration_ids
                else frozenset(),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return StartRunOutput(run_id=run_id)
