"""Supply's update-handler factory (Supply-local body).

Hand-rolls the load + authorize + fold + decide + append cycle that
the cross-BC `make_update_handler` does for every other update-style
slice, because the Supply decider takes one extra kwarg the cross-
BC factory doesn't know about: a `triggered_by: TriggeredBy`
discriminated-union attribution UUID. Per
[[project_fold_symmetry_design]], every Supply event payload pairs
`trigger` with `triggered_by`, and the tier (Actor / Monitor /
Scheduler) of the typed value MUST match the trigger string. The
cross-BC factory has no hook to inject per-aggregate extras into
the decider call, so the Supply factory owns the body.

## Hoist trigger

10a-a shipped one update-style handler (`mark_supply_available`)
longhand because rule-of-three hadn't fired yet. 10a-b adds 4 more
transition handlers (degrade / mark_unavailable / mark_recovering /
restore). Five identical longhand bodies = clear rule-of-three
signal; this factory hoists the shared scaffolding so each slice's
handler.py shrinks from ~120 lines to a 7-line `bind` that supplies
two strings and the decider. Mirrors `_asset_update_handler` (Asset
hoisted after 4 byte-identical slices) and Subject's
`_update_handler`.

## Per-aggregate, not per-BC

Supply is a single-aggregate BC today; the factory still scopes to
the Supply aggregate (not the BC) so a future Supply-sibling
aggregate would get its own factory rather than parameterizing this
one. Same per-aggregate scoping rationale as
`_asset_update_handler`.

## triggered_by injection

`triggered_by_fn(command, principal_id) -> TriggeredBy` produces the
typed attribution UUID for each invocation. The default extractor
wraps `principal_id` in `ActorId` (the Operator case, used by every
operator-driven slice). Monitor-driven `observe_supply_status`
overrides with a function that reads `MonitorSourceId` off the
command, since the principal is the in-process adapter, not the
operator whose token was attached to the request.

The transition slices carry `reason: str` alongside `supply_id`.
That field IS captured on the emitted event payload but is
intentionally NOT logged at the handler boundary (the event-store
stream is the source of truth for audit; handler log lines stay
shape-stable across slices). Same convention as Asset's condition
slices.
"""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from datetime import datetime

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyEvent,
    TriggeredBy,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.supply.errors import UnauthorizedError

_STREAM_TYPE = "Supply"


class _UpdateHandler(Protocol):
    """The factory's return shape."""

    async def __call__(
        self,
        command: Any,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _default_triggered_by(_command: Any, principal_id: UUID) -> TriggeredBy:
    """Operator-triggered slices use the request principal as ActorId."""
    return ActorId(principal_id)


def make_supply_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SupplyEvent]],
    triggered_by_fn: Callable[[Any, UUID], TriggeredBy] = _default_triggered_by,
) -> _UpdateHandler:
    """Build an update-style handler for one Supply transition slice.

    `decide_fn` MUST accept a `triggered_by` kwarg in addition to the
    cross-BC `(state, command, now)` triple; the factory threads it
    in from `triggered_by_fn(command, principal_id)`. Per-slice
    deciders type the kwarg as the specific NewType they expect
    (`ActorId` for operator slices, `MonitorSourceId` for the Monitor
    slice).
    """
    log = get_logger(log_prefix)

    async def handler(
        command: Any,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        target_id: UUID = command.supply_id

        log.info(
            f"{log_prefix}.start",
            command_name=command_name,
            supply_id=str(target_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=command_name,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            log.info(
                f"{log_prefix}.denied",
                command_name=command_name,
                supply_id=str(target_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now: datetime = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=target_id,
        )
        history: list[SupplyEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        triggered_by = triggered_by_fn(command, principal_id)
        domain_events = decide_fn(state=state, command=command, now=now, triggered_by=triggered_by)

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=command_name,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=target_id,
            expected_version=current_version,
            events=new_events,
        )

        log.info(
            f"{log_prefix}.success",
            command_name=command_name,
            supply_id=str(target_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler


__all__ = ["make_supply_update_handler"]
