"""Application handler for the `register_asset` slice.

Same shape as `register_actor` / `register_subject` / `define_zone`
/ `define_conduit` / `define_policy` / `define_family` — the
locked cross-BC create-style command pattern (now 7th instance).

The cross-BC create-style template extraction stays parked per the
post-domain-audit (defer hoisting until divergence pressure or
~10 instances; we're at 7).

When `command.model_id is not None` the handler loads the Model
stream via `load_model` BEFORE invoking the decider and raises
`ModelNotFoundError` (mapped to HTTP 404 by the BC's exception
handler tuple) when the stream returns no state. This is a load-
only cross-BC dependency; no Model snapshot is threaded into the
decider because the subset invariant is vacuously satisfied at
register-time per Lock B of the model-binding design memo.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import event_type_name, to_payload
from cora.equipment.aggregates.model import ModelNotFoundError, load_model
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "RegisterAsset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_asset handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.
    """

    async def __call__(
        self,
        command: RegisterAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_asset handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_asset handler closed over the shared deps."""

    async def handler(
        command: RegisterAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_asset.start",
            command_name=_COMMAND_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "register_asset.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        if command.model_id is not None:
            model = await load_model(deps.event_store, command.model_id)
            if model is None:
                _log.info(
                    "register_asset.model_not_found",
                    command_name=_COMMAND_NAME,
                    principal_id=str(principal_id),
                    correlation_id=str(correlation_id),
                    causation_id=str(causation_id) if causation_id is not None else None,
                    model_id=str(command.model_id),
                )
                raise ModelNotFoundError(command.model_id)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_asset.success",
            command_name=_COMMAND_NAME,
            asset_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
