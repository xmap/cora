"""Application handler for the `announce_language_model_retirement` slice.

Built on the hoisted `make_language_model_update_handler` factory
along with the 3 other LanguageModel transition slices (approve /
retire / deprecate). Single-source from Approved; the decider's guard
enforces this, the factory is source-set-agnostic.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._language_model_update_handler import make_language_model_update_handler
from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)
from cora.agent.features.announce_language_model_retirement.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every announce_language_model_retirement handler implements."""

    async def __call__(
        self,
        command: AnnounceLanguageModelRetirement,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an announce_language_model_retirement handler closed over the shared deps."""
    return make_language_model_update_handler(
        deps,
        command_name="AnnounceLanguageModelRetirement",
        log_prefix="announce_language_model_retirement",
        decide_fn=decide,
    )
