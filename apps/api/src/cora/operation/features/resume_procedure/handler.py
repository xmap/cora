"""Application handler for the `resume_procedure` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind, mirroring resume_run.

The off-diagonal guard (refuse to resume while the parent Run is `Held`)
is a cross-aggregate Run read added in a follow-up slice; it will replace
this factory bind with a custom handler (the factory loads exactly one
event-store stream). Until then the decider's status guard
(`Held -> Running`) is the only gate.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._procedure_update_handler import make_procedure_update_handler
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.decider import decide


class Handler(Protocol):
    """Callable interface every resume_procedure handler implements."""

    async def __call__(
        self,
        command: ResumeProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_procedure handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="ResumeProcedure",
        log_prefix="resume_procedure",
        decide_fn=decide,
    )
