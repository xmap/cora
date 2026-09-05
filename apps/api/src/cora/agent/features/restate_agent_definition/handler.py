"""Application handler for the `restate_agent_definition` slice.

Built on the hoisted `make_agent_update_handler` factory, like every other
single-stream Agent mutation.

No approval gate here, deliberately, even though a restatement can name a
LanguageModel brain. `define_agent` gates a brain at DEFINITION, and
`seed_agent` gates the shipped fleet at first write; a restatement that names
an unapproved model would slip past both. That gap is real and is left open
on purpose for now: the only restatements this slice exists to serve name
Rule brains, which have no catalog decision to be subject to, and wiring the
lookup into this handler before anything needs it would add a dependency for
a case no caller has. Closing it is a one-line reuse of
`_require_approved_brain` the moment a LanguageModel restatement is wanted.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.agent.features.restate_agent_definition.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every restate_agent_definition handler implements."""

    async def __call__(
        self,
        command: RestateAgentDefinition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a restate_agent_definition handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="RestateAgentDefinition",
        log_prefix="restate_agent_definition",
        decide_fn=decide,
    )
