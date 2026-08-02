"""Allocation's update-handler factory (thin wrapper + actor-stamping variant).

Mirrors `cora.agent._language_model_update_handler` per the
per-aggregate factory convention. Two transition slices bind through
the thin wrapper (`update_allocation_ceiling`, `void_allocation`);
`activate_allocation` binds through the actor-stamping variant
because the fold records `(activated_at, activated_by)` per
[[project_fold_symmetry_design]]. `seal_allocation` stays longhand:
it awaits the injected TotalSpendReader between load and decide,
which no factory expresses.

## Allocation-side knobs closed over

  - `stream_type = "Allocation"`.
  - `target_id_attr = "allocation_id"` -- every Allocation transition
    command exposes `allocation_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the budget BC (the
    BC's application-error namespace, so a budget 403 stays one class
    in log search).
  - The four codec functions imported from
    `cora.budget.aggregates.allocation`.

`extra_log_fields` is a per-slice optional extractor for command-
specific fields the structured log should emit, same contract as the
Agent factory.

The actor variant mirrors `make_agent_actor_update_handler`
byte-for-byte modulo the Allocation-specific defaults; the body
duplicates `make_update_handler`'s flow because `principal_id` only
enters scope at handler-call time, not at factory-build time.

NOTE (superseded): `make_update_handler` now takes an optional
`actor_kwarg` and threads the principal itself, so this body no longer
HAS to be a copy. Collapsing this factory onto the shared core is a
recorded follow-up, deliberately not done in the commit that added the
parameter so that change stayed reviewable.
"""

from collections.abc import Callable, Sequence
from datetime import datetime  # noqa: TC003 (runtime-imported for clarity)
from typing import Any, Protocol
from uuid import UUID

from cora.budget.aggregates.allocation import (
    AllocationEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.budget.errors import UnauthorizedError
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.infrastructure.update_handler import make_update_handler
from cora.shared.identity import ActorId

_STREAM_TYPE = "Allocation"
_TARGET_ID_ATTR = "allocation_id"


def make_allocation_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AllocationEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Allocation slice (fold-NEITHER posture)."""
    return make_update_handler(
        deps,
        stream_type=_STREAM_TYPE,
        target_id_attr=_TARGET_ID_ATTR,
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        extra_log_fields=extra_log_fields,
    )


class _ActorUpdateHandler(Protocol):
    """Callable shape returned by `make_allocation_actor_update_handler`.

    Mirrors the cross-BC factory's `_UpdateHandler` shape so per-slice
    `Handler` Protocols (which are narrower in `command`) keep
    assigning without explicit casts.
    """

    async def __call__(
        self,
        command: Any,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def make_allocation_actor_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AllocationEvent]],
    actor_kwarg: str,
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
) -> _ActorUpdateHandler:
    """Build an actor-stamping update handler for one Allocation slice.

    `actor_kwarg` is the decider's `<verb>_by` parameter name; the
    handler passes the envelope's `principal_id` (wrapped in `ActorId`)
    under that name on every call. Used by fold-symmetry slices
    (`activate_allocation`) whose events carry a folded attribution
    half on the payload.
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
        target_id: UUID = getattr(command, _TARGET_ID_ATTR)
        extras: dict[str, Any] = extra_log_fields(command) if extra_log_fields is not None else {}

        log.info(
            f"{log_prefix}.start",
            command_name=command_name,
            **{_TARGET_ID_ATTR: str(target_id)},
            **extras,
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
                **{_TARGET_ID_ATTR: str(target_id)},
                **extras,
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
        history: list[AllocationEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide_fn(
            state=state,
            command=command,
            now=now,
            **{actor_kwarg: ActorId(principal_id)},
        )

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
            **{_TARGET_ID_ATTR: str(target_id)},
            **extras,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler


__all__ = ["make_allocation_actor_update_handler", "make_allocation_update_handler"]
