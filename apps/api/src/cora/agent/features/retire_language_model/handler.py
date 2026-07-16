"""Application handler for the `retire_language_model` slice.

Built on the hoisted `make_language_model_update_handler` factory
along with the 3 other LanguageModel transition slices (approve /
announce-retirement / deprecate). Source set is
`{Approved, RetirementAnnounced}`; the decider's guard enforces this,
the factory is source-set-agnostic.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._language_model_update_handler import make_language_model_update_handler
from cora.agent.features.retire_language_model.command import RetireLanguageModel
from cora.agent.features.retire_language_model.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every retire_language_model handler implements."""

    async def __call__(
        self,
        command: RetireLanguageModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a retire_language_model handler closed over the shared deps."""
    return make_language_model_update_handler(
        deps,
        command_name="RetireLanguageModel",
        log_prefix="retire_language_model",
        decide_fn=decide,
    )
