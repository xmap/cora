"""Application handler for the `record_witnessed_run_outcome` slice.

Update-style handler. Canonical body lives in
`cora.run._run_update_handler.make_run_update_handler`; this module is a
thin slice-specific bind, same shape as `complete_run/handler.py` and
`abort_run/handler.py`.

Per the roadmap's anti-scope: no REST route, no MCP tool reach this
handler (see `route.py` / `tool.py`, both stubs, mirroring
`record_witnessed_run`'s own in-process-only lock). The authorized path
in is the bound handler on `RunHandlers.record_witnessed_run_outcome`,
called only by the in-process RunWitness runtime as a seeded Agent
principal.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run._run_update_handler import make_run_update_handler
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.record_witnessed_run_outcome.decider import decide


class Handler(Protocol):
    """Callable interface every record_witnessed_run_outcome handler implements."""

    async def __call__(
        self,
        command: RecordWitnessedRunOutcome,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a record_witnessed_run_outcome handler closed over the shared deps."""
    return make_run_update_handler(
        deps,
        command_name="RecordWitnessedRunOutcome",
        log_prefix="record_witnessed_run_outcome",
        decide_fn=decide,
    )
