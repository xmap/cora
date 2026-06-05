"""MCP tool for the `update_asset_partition_rule` slice.

Mirror of the HTTP route: the tool accepts `asset_id` and an optional
`partition_rule` dict that matches the JSON discriminated-union shape
(kind + kind-specific fields). When partition_rule is None, the rule
is cleared. Domain errors (InvalidPartitionRuleError, self-reference,
nesting, asset-not-found, asset-cannot-update) propagate to FastMCP
as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.aggregates._partition_rule import (
    InvalidPartitionRuleError,
    partition_rule_from_payload,
)
from cora.equipment.features.update_asset_partition_rule.command import (
    UpdateAssetPartitionRule,
)
from cora.equipment.features.update_asset_partition_rule.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_asset_partition_rule` tool on the given MCP server."""

    @mcp.tool(
        name="update_asset_partition_rule",
        description=(
            "Update a PseudoAxis Asset's partition rule, which decomposes "
            "an operator-commanded virtual-axis value into setpoints on "
            "N constituent motor axes. Partition rule is a discriminated "
            "union of 5 closed shapes (Affine, Aggregation, LookupTable, "
            "CompositePartition, SolverReference). Pass partition_rule as "
            "a dict with 'kind' discriminator + kind-specific fields. "
            "Pass None to clear the rule. The rule must not self-reference "
            "or nest to another PseudoAxis. Asset must exist and be of "
            "Family PseudoAxis and not Decommissioned."
        ),
    )
    async def update_asset_partition_rule_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        partition_rule: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "Partition rule dict with 'kind' discriminator and kind-specific fields, "
                    "or None to clear the rule. "
                    'Example for Affine: {"kind": "Affine", "gain": 2.0, "offset": 0.0}. '
                    'Example for Aggregation: {"kind": "Aggregation", '
                    '"aggregator_kind": "Sum", "constituent_count": 2}.'
                ),
            ),
        ] = None,
    ) -> None:
        # Convert the dict to a typed PartitionRule VO if not None.
        # partition_rule_from_payload will re-run __post_init__ validators
        # and raise InvalidPartitionRuleError on malformed input.
        typed_rule = None
        if partition_rule is not None:
            try:
                typed_rule = partition_rule_from_payload(partition_rule)
            except InvalidPartitionRuleError:
                # Let the error propagate to FastMCP; it surfaces as isError: true
                # to the LLM with the sub_code and reason in the error message.
                raise

        handler = get_handler()
        await handler(
            UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=typed_rule),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
