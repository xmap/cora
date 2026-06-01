"""Application handler for the `version_model` slice.

Update-style handler shape: load + fold + decide + append. Mirrors
the version_family precedent (no idempotency wrapping; the command
carries `model_id` and `version_tag` and the handler logs both for
diagnostic visibility).

Not idempotency-wrapped: re-versioning with the same tag is still a
real revision the operator wanted (matches version_family's
re-attestation stance). Domain-idempotent via `ModelCannotVersionError`
on retry from `Deprecated`.

NO cross-BC family lookup here: per the Model design memo Lock,
`version_model` accepts whatever `declared_families` the caller
supplies without round-tripping the Family read repo. Incremental
declared-family edits use `add_model_family`, which is where the
cross-BC `list_family_ids` check lives. The wholesale replacement
that `version_model` performs is treated as authoritative operator
intent at version time.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.model import (
    ModelEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.version_model.command import VersionModel
from cora.equipment.features.version_model.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Model"
_COMMAND_NAME = "VersionModel"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every version_model handler implements."""

    async def __call__(
        self,
        command: VersionModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a version_model handler closed over the shared deps."""

    async def handler(
        command: VersionModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "version_model.start",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
            version_tag=command.version_tag,
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
                "version_model.denied",
                command_name=_COMMAND_NAME,
                model_id=str(command.model_id),
                version_tag=command.version_tag,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.model_id,
        )
        history: list[ModelEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now)

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
            stream_id=command.model_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "version_model.success",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
