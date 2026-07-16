"""Application handler for the `define_language_model` slice.

Single-stream genesis on the Agent BC's LanguageModel stream type.
Unlike `define_agent` there is NO cross-BC Actor co-write: a catalog
entry is configuration, not a principal, so nothing about it belongs
on an Access BC stream.

One deviation from the simple create-style template: the command may
carry a caller-supplied `language_model_id` (deployments seed the
catalog from configuration and need stable ids across environments).
The handler therefore loads the target stream BEFORE deciding so the
decider's genesis guard rejects an id collision with
`LanguageModelAlreadyExistsError`; the `expected_version=0` append
backstops the race where two callers define the same id
concurrently. When the command carries None the handler mints a
UUIDv7 via the IdGenerator port, the `define_agent` posture.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.agent.aggregates.language_model import (
    event_type_name,
    load_language_model,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features.define_language_model.command import DefineLanguageModel
from cora.agent.features.define_language_model.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "LanguageModel"
_COMMAND_NAME = "DefineLanguageModel"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_language_model handler -- what `bind()` returns.

    Returns the new catalog entry's UUID (caller-supplied when the
    command carried one, handler-minted otherwise). Has no
    idempotency_key kwarg; `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: DefineLanguageModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_language_model handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineLanguageModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_language_model handler closed over the shared deps."""

    async def handler(
        command: DefineLanguageModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_language_model.start",
            command_name=_COMMAND_NAME,
            provider=command.provider,
            model=command.model,
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
                "define_language_model.denied",
                command_name=_COMMAND_NAME,
                provider=command.provider,
                model=command.model,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = (
            command.language_model_id
            if command.language_model_id is not None
            else deps.id_generator.new_id()
        )
        now = deps.clock.now()

        # Load the target stream so a caller-supplied id that already
        # has events trips the decider's genesis guard (a handler-minted
        # UUIDv7 folds to None here).
        state = await load_language_model(deps.event_store, new_id)

        domain_events = decide(
            state=state,
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
            "define_language_model.success",
            command_name=_COMMAND_NAME,
            language_model_id=str(new_id),
            provider=command.provider,
            model=command.model,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
