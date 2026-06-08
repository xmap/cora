"""Application handler for the `append_calibration_revision` slice.

Update-style handler (loads the Calibration aggregate then appends a
new revision event). Per the design memo, this slice IS Idempotency-
Key wrapped: agent subscribers will be the primary callers
(for example, a future `RotationCenterRefiner` that subscribes to terminal
Run events and computes a `tomopy.find_center_vo` refinement),
needing exactly-once-effective semantics across retries.

Returns the newly-minted `revision_id` so the caller (operator UI,
agent subscriber, integration script) can record a stable PROV-O
anchor for the value just appended.

Per [[project_update_handler_pattern]], the
`make_calibration_update_handler` factory is NOT hoisted yet:
only one update slice ships here (`append_calibration_revision`). The factory
will emerge when a second update transition lands (for example, a future
`promote_calibration_revision`).
"""

from typing import Protocol
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    CalibrationNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.calibration.aggregates.calibration.evolver import fold
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.append_calibration_revision.command import (
    AppendCalibrationRevision,
)
from cora.calibration.features.append_calibration_revision.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Calibration"
_COMMAND_NAME = "AppendCalibrationRevision"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare append_calibration_revision handler — what `bind()` returns.

    Returns the new revision's UUID. Has no idempotency_key kwarg;
    `with_idempotency` at wire.py adds it (the design memo requires
    wrapping for the agent-subscriber caller pattern).
    """

    async def __call__(
        self,
        command: AppendCalibrationRevision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """append_calibration_revision handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: AppendCalibrationRevision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build an append_calibration_revision handler closed over the shared deps."""

    async def handler(
        command: AppendCalibrationRevision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "append_calibration_revision.start",
            command_name=_COMMAND_NAME,
            calibration_id=str(command.calibration_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            status=command.status.value,
            source_kind=type(command.source).__name__,
            supersedes_revision_id=(
                str(command.supersedes_revision_id)
                if command.supersedes_revision_id is not None
                else None
            ),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "append_calibration_revision.denied",
                command_name=_COMMAND_NAME,
                calibration_id=str(command.calibration_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.calibration_id)
        state = fold([from_stored(s) for s in stored])
        if state is None:
            raise CalibrationNotFoundError(command.calibration_id)

        now = deps.clock.now()
        new_revision_id = deps.id_generator.new_id()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            new_revision_id=new_revision_id,
            established_by=ActorId(principal_id),
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
            stream_id=command.calibration_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "append_calibration_revision.success",
            command_name=_COMMAND_NAME,
            calibration_id=str(command.calibration_id),
            revision_id=str(new_revision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_revision_id

    return handler
