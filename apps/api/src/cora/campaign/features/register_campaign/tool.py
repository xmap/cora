"""MCP tool for the `register_campaign` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.campaign.aggregates.campaign import (
    CAMPAIGN_DESCRIPTION_MAX_LENGTH,
    CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
    CAMPAIGN_NAME_MAX_LENGTH,
    CampaignIntent,
)
from cora.campaign.features.register_campaign.command import RegisterCampaign
from cora.campaign.features.register_campaign.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.identifier import Identifier


class RegisterCampaignOutput(BaseModel):
    """Structured output of the `register_campaign` MCP tool."""

    campaign_id: UUID


def _refs_from_dicts(refs: list[dict[str, Any]] | None) -> frozenset[Identifier]:
    if not refs:
        return frozenset()
    return frozenset(Identifier(scheme=str(r["scheme"]), value=str(r["value"])) for r in refs)


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="register_campaign",
        description=(
            "Register a new Campaign (lands in 'Planned' status). A Campaign "
            "is the operator-declared coordinated container above Run "
            "(series of measurements over time, parametric sweep, "
            "coordinated multi-modal or multi-Subject acquisition, "
            "scheduling block). Closed intent-shape vocabulary "
            "(Series / Sweep / Coordination / Block); free tags carry "
            "scientific-technique vocabulary; optional external refs "
            "(proposal/btr/visit/cycle)."
        ),
    )
    async def register_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAMPAIGN_NAME_MAX_LENGTH,
                description="Operator-meaningful Campaign name.",
            ),
        ],
        intent: Annotated[
            CampaignIntent,
            Field(description="Closed intent-shape vocabulary (Series/Sweep/Coordination/Block)."),
        ],
        lead_actor_id: Annotated[
            UUID,
            Field(
                description=(
                    "REQUIRED. The Campaign's PI / lead operator (may "
                    "differ from the registering principal)."
                ),
            ),
        ],
        subject_id: Annotated[
            UUID | None,
            Field(default=None, description="Optional informational Subject reference."),
        ] = None,
        description: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=CAMPAIGN_DESCRIPTION_MAX_LENGTH,
                description="Optional free-form description.",
            ),
        ] = None,
        tags: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Optional free-form tags; each 1-50 chars.",
            ),
        ] = None,
        external_refs: Annotated[
            list[dict[str, Any]] | None,
            Field(
                default=None,
                description=(
                    "Optional anti-corruption refs; each {scheme: 'proposal', value: '12345'}."
                ),
            ),
        ] = None,
        external_id: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
                description="Optional facility-minted external id.",
            ),
        ] = None,
    ) -> RegisterCampaignOutput:
        handler = get_handler()
        campaign_id = await handler(
            RegisterCampaign(
                name=name,
                intent=intent,
                lead_actor_id=lead_actor_id,
                subject_id=subject_id,
                description=description,
                tags=frozenset(tags or []),
                external_refs=_refs_from_dicts(external_refs),
                external_id=external_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterCampaignOutput(campaign_id=campaign_id)
