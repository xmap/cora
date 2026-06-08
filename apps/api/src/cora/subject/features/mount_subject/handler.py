"""Application handler for the `mount_subject` slice.

Cross-aggregate update-style handler: load + authorize + fold + load
mount-target Asset + decide + append. Mirrors `start_run`'s handler
shape (the canonical 2-instance example of cross-aggregate
validation in CONTRIBUTING.md).

Differs from the other Subject update slices: cannot use
`make_subject_update_handler` because the decider takes an extra
`context: MountSubjectContext` parameter built from a pre-loaded
Asset. Same load-then-authorize ordering and structured logging as
the other Subject update handlers.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second call hits
`SubjectCannotMountError`). See CONTRIBUTING.md.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import AssetNotFoundError, load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.subject.errors import UnauthorizedError
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.context import MountSubjectContext
from cora.subject.features.mount_subject.decider import decide

_STREAM_TYPE = "Subject"
_COMMAND_NAME = "MountSubject"
_LOG_PREFIX = "mount_subject"

_log = get_logger(_LOG_PREFIX)


class Handler(Protocol):
    """Callable interface every mount_subject handler implements."""

    async def __call__(
        self,
        command: MountSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a mount_subject handler closed over the shared deps."""

    async def handler(
        command: MountSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        subject_id = command.subject_id
        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            subject_id=str(subject_id),
            asset_id=str(command.asset_id),
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
                f"{_LOG_PREFIX}.denied",
                command_name=_COMMAND_NAME,
                subject_id=str(subject_id),
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=subject_id,
        )
        history: list[SubjectEvent] = [from_stored(s) for s in stored]
        state: Subject | None = fold(history)

        # Cross-aggregate context (pattern per CONTRIBUTING.md).
        asset = await load_asset(deps.event_store, command.asset_id)
        if asset is None:
            raise AssetNotFoundError(command.asset_id)
        context = MountSubjectContext(asset=asset)

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            mounted_by=ActorId(principal_id),
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
            stream_id=subject_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            subject_id=str(subject_id),
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
