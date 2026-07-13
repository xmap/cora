"""Application handler for the `seal_allocation` slice.

Longhand (not factory-built): between load and decide the handler
awaits the injected `TotalSpendReader` to fold the envelope's final
spend over its own window, `[state.activated_at, now)`, which the
single-stream update factory cannot express. The allocation's
lifecycle IS the window (no calendar arithmetic): `activated_at`
comes off the loaded aggregate, `now` off the Clock port, and the
snapshot lands in the `AllocationSealed` payload as the
closing-the-books figure.

`total_spend_reader` is bound at wire time, NOT resolved from Kernel:
stage A has no instance-total spend query yet, so `wire.py` binds
`zero_total_spend` (every stage-A seal records 0.0) and stage C
replaces it with the SpendLookup-backed reader when
`find_total_spend` lands. Binding the seam now means the stage-C
subscriber and the route both flow through this one slice unchanged.

The reader is only consulted when the loaded envelope has an open
window (`activated_at` set); on the guard paths (missing stream,
non-Active status) the decider raises before the snapshot matters,
so the handler skips the ledger read entirely rather than fold a
window that never opened.

The handler threads `sealed_by=ActorId(principal_id)` into the
decider so the seal fact-act folds with its attribution half per
[[project_fold_symmetry_design]].
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.budget.aggregates.allocation import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Allocation"
_COMMAND_NAME = "SealAllocation"

_log = get_logger(__name__)


class TotalSpendReader(Protocol):
    """Folds the deployment's total recorded LLM spend over a window.

    The window is the envelope's own lifecycle: `[window_start,
    window_end)` with `window_start = activated_at` and `window_end`
    the seal instant. Stage C implements this over SpendLookup's
    `find_total_spend`; stage A binds `zero_total_spend`.
    """

    async def __call__(self, *, window_start: datetime, window_end: datetime) -> float: ...


async def zero_total_spend(*, window_start: datetime, window_end: datetime) -> float:
    """Stage-A placeholder reader: no instance-total spend query exists yet.

    Every stage-A seal records `spent_usd = 0.0`. Honest by
    construction: the figure is the reader's answer, and until stage C
    wires the SpendLookup-backed reader the ledger-backed answer is
    not available, not silently approximated.
    """
    _ = (window_start, window_end)
    return 0.0


class Handler(Protocol):
    """Callable interface every seal_allocation handler implements."""

    async def __call__(
        self,
        command: SealAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel, *, total_spend_reader: TotalSpendReader) -> Handler:
    """Build a seal_allocation handler closed over the shared deps.

    `total_spend_reader` is an explicit keyword (no default) so every
    wiring site states which ledger fold the seal snapshot records.
    """

    async def handler(
        command: SealAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "seal_allocation.start",
            command_name=_COMMAND_NAME,
            allocation_id=str(command.allocation_id),
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
                "seal_allocation.denied",
                command_name=_COMMAND_NAME,
                allocation_id=str(command.allocation_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.allocation_id,
        )
        history = [from_stored(s) for s in stored]
        state = fold(history)

        spent_usd = 0.0
        if state is not None and state.activated_at is not None:
            spent_usd = await total_spend_reader(
                window_start=state.activated_at,
                window_end=now,
            )

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            spent_usd=spent_usd,
            sealed_by=ActorId(principal_id),
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
            stream_id=command.allocation_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "seal_allocation.success",
            command_name=_COMMAND_NAME,
            allocation_id=str(command.allocation_id),
            spent_usd=spent_usd,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
