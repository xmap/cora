"""Application handler for the `hold_procedure` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind, mirroring abort_procedure /
truncate_procedure.

The command's `reason` field IS captured on the emitted `ProcedureHeld`
event payload but is intentionally NOT logged at the handler boundary
(mirrors abort_procedure / hold_run precedent), so this slice does not
pass `extra_log_fields`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._procedure_update_handler import make_procedure_update_handler
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.decider import decide


class Handler(Protocol):
    """Callable interface every hold_procedure handler implements."""

    async def __call__(
        self,
        command: HoldProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a hold_procedure handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="HoldProcedure",
        log_prefix="hold_procedure",
        decide_fn=decide,
    )
