"""Application handler for the `get_model` query slice.

Cross-BC query-handler shape, mirrored from `get_family` /
`get_actor` / `get_subject`:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_model(...)              -> Model | None  (fold-on-read)
    3. return Model | None          -> caller maps None to 404 / isError

Unlike `get_family`, no `ModelView` wrapper is needed: the Model
summary projection does NOT carry per-FSM-transition timestamps
(versioned_at, deprecated_at), so there is no projection-sourced
metadata to fold into the response. The route / tool layer reads
`Model` directly. If a future projection-schema addition lands
(transition timestamps), the same `FamilyView`-style bundle would
be introduced here without changing the slice contract.

Query handlers do NOT emit `causation_id` log fields, since queries
have no causation chain (they don't emit events that downstream
commands react to). Same convention as `get_family` /
`get_actor` / `get_subject`.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.model import Model, load_model
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_model.query import GetModel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetModel"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_model handler implements."""

    async def __call__(
        self,
        query: GetModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Model | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_model handler closed over the shared deps."""

    async def handler(
        query: GetModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Model | None:
        _log.info(
            "get_model.start",
            query_name=_QUERY_NAME,
            model_id=str(query.model_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_model.denied",
                query_name=_QUERY_NAME,
                model_id=str(query.model_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        model = await load_model(deps.event_store, query.model_id)
        _log.info(
            "get_model.success",
            query_name=_QUERY_NAME,
            model_id=str(query.model_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=model is not None,
        )
        return model

    return handler
