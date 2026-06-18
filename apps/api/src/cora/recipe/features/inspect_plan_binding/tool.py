"""MCP tool for the `inspect_plan_binding` query slice.

Surfaces the same handler the REST route uses. Returns a
structured `InspectPlanBindingOutput`. NotFound errors raised by
the handler propagate as FastMCP-wrapped `isError: true` with the
error message text, matching the REST 404 behaviour in MCP's
error idiom.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.features.inspect_plan_binding.handler import Handler
from cora.recipe.features.inspect_plan_binding.query import InspectPlanBinding


class WiredAssetItem(BaseModel):
    """Per-wired-Asset binding contribution on the MCP wire."""

    asset_id: UUID
    asset_name: str
    condition: str | None
    lifecycle: str
    family_ids: list[UUID]
    contributed_affordances: list[str]


class CandidateAssetItem(BaseModel):
    """Per-Asset candidate for a missing affordance on the MCP wire.

    `contributing_family_ids` lists only the Families that declare
    the parent missing affordance, distinct from
    `WiredAssetItem.family_ids` which lists the full set.
    """

    asset_id: UUID
    asset_name: str
    condition: str | None
    lifecycle: str
    contributing_family_ids: list[UUID] = Field(
        ...,
        description=(
            "Subset of the candidate's Families that declare the parent "
            "missing affordance, NOT the candidate's full Family set."
        ),
    )


class MissingAffordanceCandidatesItem(BaseModel):
    """Per-missing-affordance group on the MCP wire."""

    affordance: str
    candidates: list[CandidateAssetItem]


class InspectPlanBindingOutput(BaseModel):
    """Structured output of the `inspect_plan_binding` MCP tool."""

    practice_id: UUID
    method_id: UUID
    capability_id: UUID | None
    method_needed_family_ids: list[UUID]
    capability_required_affordances: list[str]
    wired_assets: list[WiredAssetItem]
    missing_family_ids: list[UUID]
    missing_affordances: list[str]
    missing_affordance_candidates: list[MissingAffordanceCandidatesItem]
    binding_status: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `inspect_plan_binding` tool on the given MCP server."""

    @mcp.tool(
        name="inspect_plan_binding",
        description=(
            "Preview the diagnostic for a candidate Plan binding without "
            "defining it. Returns the wired Assets' conditions, their "
            "contributed affordances, any missing families or affordances, "
            "and per missing affordance the other facility Assets whose "
            "Families could cover the requirement (candidate enumeration). "
            "Read-only: no events are emitted and no Plan "
            "is created."
        ),
    )
    async def inspect_plan_binding_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        practice_id: Annotated[
            UUID,
            Field(description="Practice the candidate Plan would bind."),
        ],
        asset_ids: Annotated[
            list[UUID],
            Field(description="Candidate wired-Asset ids.", min_length=1),
        ],
    ) -> InspectPlanBindingOutput:
        handler = get_handler()
        view = await handler(
            InspectPlanBinding(
                practice_id=practice_id,
                asset_ids=frozenset(asset_ids),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return InspectPlanBindingOutput(
            practice_id=view.practice_id,
            method_id=view.method_id,
            capability_id=view.capability_id,
            method_needed_family_ids=sorted(view.method_needed_family_ids, key=str),
            capability_required_affordances=sorted(
                a.value for a in view.capability_required_affordances
            ),
            wired_assets=[
                WiredAssetItem(
                    asset_id=item.asset_id,
                    asset_name=item.asset_name,
                    condition=item.condition.value if item.condition is not None else None,
                    lifecycle=item.lifecycle.value,
                    family_ids=sorted(item.family_ids, key=str),
                    contributed_affordances=sorted(a.value for a in item.contributed_affordances),
                )
                for item in view.wired_assets
            ],
            missing_family_ids=sorted(view.missing_family_ids, key=str),
            missing_affordances=sorted(a.value for a in view.missing_affordances),
            missing_affordance_candidates=[
                MissingAffordanceCandidatesItem(
                    affordance=entry.affordance.value,
                    candidates=[
                        CandidateAssetItem(
                            asset_id=candidate.asset_id,
                            asset_name=candidate.asset_name,
                            condition=(
                                candidate.condition.value
                                if candidate.condition is not None
                                else None
                            ),
                            lifecycle=candidate.lifecycle.value,
                            contributing_family_ids=sorted(
                                candidate.contributing_family_ids, key=str
                            ),
                        )
                        for candidate in entry.candidates
                    ],
                )
                for entry in view.missing_affordance_candidates
            ],
            binding_status=view.binding_status.value,
        )
