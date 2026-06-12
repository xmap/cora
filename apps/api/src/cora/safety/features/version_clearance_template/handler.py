"""Application handler for the `version_clearance_template` slice.

Update-style handler (loads the ClearanceTemplate aggregate then appends a
`ClearanceTemplateVersioned` event). Additive within `Active`: there is no
FSM transition. The decider enforces both the monotonic `new_version` rule
and the parent same-facility chain check.

Cross-aggregate parent lookup is threaded via `ClearanceTemplateLookup`:
the handler resolves `supersedes_template_id` to a row in
`proj_safety_clearance_template_summary`. `None` means the parent template
is not visible to this BC; the decider translates that to
`ClearanceTemplateNotFoundError` (404). A non-None result whose
`facility_code` disagrees with the loaded aggregate raises
`ClearanceTemplateFacilityMismatchError` (per L5).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance_template import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.safety.features.version_clearance_template.decider import decide
from cora.shared.identity import ActorId

_STREAM_TYPE = "ClearanceTemplate"
_COMMAND_NAME = "VersionClearanceTemplate"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare version_clearance_template handler  --  what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.

    `causation_id` is the id of the event/message that triggered
    this command (None for HTTP / MCP root calls; sagas / process
    managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: VersionClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """version_clearance_template handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: VersionClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a version_clearance_template handler closed over the shared deps."""

    async def handler(
        command: VersionClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "version_clearance_template.start",
            command_name=_COMMAND_NAME,
            template_id=str(command.template_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            new_version=command.new_version,
            supersedes_template_id=str(command.supersedes_template_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "version_clearance_template.denied",
                command_name=_COMMAND_NAME,
                template_id=str(command.template_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.template_id)
        state = fold([from_stored(s) for s in stored])

        parent_lookup_result = await deps.clearance_template_lookup.lookup(
            command.supersedes_template_id
        )

        now = deps.clock.now()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            versioned_by=ActorId(principal_id),
            parent_lookup_result=parent_lookup_result,
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
            stream_id=command.template_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "version_clearance_template.success",
            command_name=_COMMAND_NAME,
            template_id=str(command.template_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return None

    return handler
