"""Application handler for the `approve_language_model` slice.

Built on the hoisted `make_language_model_update_handler` factory
along with the 3 other LanguageModel transition slices
(announce-retirement / retire / deprecate). Single-source from
Defined; the decider's guard enforces this, the factory is
source-set-agnostic.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._language_model_update_handler import make_language_model_update_handler
from cora.agent.features.approve_language_model.command import ApproveLanguageModel
from cora.agent.features.approve_language_model.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every approve_language_model handler implements."""

    async def __call__(
        self,
        command: ApproveLanguageModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an approve_language_model handler closed over the shared deps."""
    return make_language_model_update_handler(
        deps,
        command_name="ApproveLanguageModel",
        log_prefix="approve_language_model",
        decide_fn=decide,
    )
