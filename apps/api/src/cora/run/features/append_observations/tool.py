"""MCP tool for the `append_observations` slice.

## value / categorical_value exclusivity checked here, not just in the handler

Unlike `ObservationRequest` (route.py), this tool takes `value` /
`categorical_value` as flat parameters rather than a nested Pydantic
model, so there is no `model_validator` attachment point for the
cross-field exclusivity check. Checking it here, before `get_handler()`
is even called, matches the REST route's failure POINT (ahead of authz)
rather than relying solely on the handler's later
`InvalidObservationShapeError` check -- otherwise an MCP caller would
fail later, and after an unnecessary authz round-trip, than an
equivalent REST caller for the identical mistake.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.aggregates.run import InvalidObservationShapeError
from cora.run.features.append_observations.command import (
    AppendObservations,
    ObservationInput,
)
from cora.run.features.append_observations.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_observations` tool on the given MCP server.

    Single-entry shape for MCP simplicity (one tool call = one
    observation). HTTP route accepts batches; agents typically reason
    about one observation at a time and the per-call overhead is fine.
    """

    @mcp.tool(
        name="append_observations",
        description=(
            "Append one polymorphic sensor / motor observation to a Run's "
            "observation logbook. Lazy-opens the logbook on first call. "
            "`sampling_procedure` discriminates baseline (snapshot at "
            "run boundary) vs monitor (sub-Hz time-series). Exactly one "
            "of value (numeric) or categorical_value (enum label) must "
            "be set. Rejects when Run is in a terminal status."
        ),
    )
    async def append_observations_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[UUID, Field(description="Target run's id.")],
        channel_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=255,
                description="Sensor or motor identifier.",
            ),
        ],
        sampled_at: Annotated[
            datetime,
            Field(description="When the sensor captured the value (SOSA phenomenonTime)."),
        ],
        sampling_procedure: Annotated[
            Literal["baseline", "monitor"],
            Field(
                description=(
                    "SOSA-aligned discriminator. 'baseline' = snapshot "
                    "at run boundary; 'monitor' = sub-Hz time-series "
                    "during the run (Bluesky monitor stream)."
                ),
            ),
        ],
        value: Annotated[
            float | None,
            Field(
                default=None,
                allow_inf_nan=False,
                description=(
                    "Numeric observation value. Exactly one of value / "
                    "categorical_value must be set."
                ),
            ),
        ] = None,
        categorical_value: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=64,
                description=(
                    "Enum-label observation value (the facility's own "
                    "substrate label, e.g. 'Fly', 'Both'). Exactly one of "
                    "value / categorical_value must be set."
                ),
            ),
        ] = None,
        units: Annotated[
            str | None,
            Field(default=None, max_length=64, description="Optional unit string."),
        ] = None,
        is_simulated: Annotated[
            bool,
            Field(
                default=False,
                description=(
                    "Provenance flag. True only when a simulator / replay "
                    "feeder produced this value; defaults to False (real). "
                    "Closed-loop rules disqualify simulated values."
                ),
            ),
        ] = False,
    ) -> int:
        if (value is None) == (categorical_value is None):
            raise InvalidObservationShapeError(value=value, categorical_value=categorical_value)
        handler = get_handler()
        entry = ObservationInput(
            event_id=uuid4(),
            channel_name=channel_name,
            value=value,
            categorical_value=categorical_value,
            sampled_at=sampled_at,
            sampling_procedure=sampling_procedure,
            units=units,
            is_simulated=is_simulated,
        )
        return await handler(
            AppendObservations(run_id=run_id, entries=(entry,)),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
