"""Application handler for the `update_method_launch_spec` slice.

Update-style handler. Canonical body lives in
`cora.recipe._method_update_handler.make_method_update_handler`; this
module is a thin slice-specific bind. No cross-BC load is needed (the
decider cross-checks `state.parameters_schema`, already on Method
state), so unlike `update_method_parameters_schema` this uses the
generic factory.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.update_method_launch_spec.command import UpdateMethodLaunchSpec
from cora.recipe.features.update_method_launch_spec.decider import decide


class Handler(Protocol):
    """Callable interface every update_method_launch_spec handler implements."""

    async def __call__(
        self,
        command: UpdateMethodLaunchSpec,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_method_launch_spec handler closed over the shared deps."""
    return make_method_update_handler(
        deps,
        command_name="UpdateMethodLaunchSpec",
        log_prefix="update_method_launch_spec",
        decide_fn=decide,
    )
