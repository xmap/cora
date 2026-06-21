"""Application handler for the `withdraw_edition` slice.

Update-style handler. Pre-load order per design memo L17:

  1. UnauthorizedError (Authorize.authorize)
  2. Load Edition stream + fold -> EditionNotFoundError if None
  3. (Cheap) status guard (EditionCannotWithdrawError)
  4. PersistentIdentifierMinter.tombstone(pid, reason) ->
     PersistentIdentifierMinterTombstoneError 502
  5. Decider emits EditionWithdrawn

The tombstone side effect runs BEFORE the append: a wire failure
aborts the command (the DOI stays Findable at DataCite; operator
escalates) without leaving a Withdrawn event behind.
"""

from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from cora.data.aggregates.edition import (
    EditionCannotWithdrawError,
    EditionEvent,
    EditionNotFoundError,
    EditionStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.aggregates.edition.state import (
    EditionWithdrawnWithoutPersistentIdError,
    PersistentIdentifierMinterTombstoneError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.data.features.withdraw_edition.context import WithdrawEditionContext
from cora.data.features.withdraw_edition.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMinter

_STREAM_TYPE = "Edition"
_COMMAND_NAME = "WithdrawEdition"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare withdraw_edition handler, what `bind()` returns."""

    async def __call__(
        self,
        command: WithdrawEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a withdraw_edition handler closed over the shared deps."""
    minter = cast("PersistentIdentifierMinter", deps.data.persistent_identifier_minter)  # type: ignore[attr-defined]

    async def handler(
        command: WithdrawEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "withdraw_edition.start",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
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
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.edition_id,
        )
        history: list[EditionEvent] = [from_stored(s) for s in stored]
        state = fold(history)
        if state is None:
            raise EditionNotFoundError(command.edition_id)

        # Cheap status guard (the decider repeats it defensively after
        # the VO check; here it short-circuits before the tombstone call).
        if state.status is not EditionStatus.PUBLISHED:
            raise EditionCannotWithdrawError(edition_id=state.id, current_status=state.status)

        # A Published Edition always carries an external_pid (set at the
        # Published transition). Defensive guard keeps the tombstone call
        # total: a Published-without-PID state is a corrupt stream.
        if state.external_pid is None:
            raise EditionWithdrawnWithoutPersistentIdError(edition_id=state.id)

        # Tombstone the DOI BEFORE appending: a wire failure aborts the
        # command (DOI stays Findable; operator escalates).
        try:
            await minter.tombstone(state.external_pid, command.withdrawal_reason)
        except PersistentIdentifierMinterTombstoneError:
            raise

        domain_events = decide(
            state=state,
            command=command,
            context=WithdrawEditionContext(),
            now=now,
            withdrawn_by=ActorId(principal_id),
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
            stream_id=command.edition_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "withdraw_edition.success",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
            external_pid=(f"{state.external_pid.scheme.value}:{state.external_pid.value}"),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
