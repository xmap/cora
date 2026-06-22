"""Agent's update-handler factory (thin wrapper + actor-stamping variant).

Hoisted at the rule-of-three trigger: the Agent BC started with 2
transition slices (`version_agent` + `deprecate_agent`); growth to
7 (+ `suspend_agent` + `resume_agent` + `grant_tool_to_agent` +
`revoke_tool_from_agent` + `update_agent_budget`) put it well past
the n=3 threshold that triggered the same hoist for Recipe's
Method / Plan / Practice + Subject + Asset + Supply + Procedure +
Caution + Clearance + Run + Campaign.

Per-aggregate scoping (not BC-wide) mirrors the Equipment / Recipe
precedent: Agent BC owns ONE aggregate today (Agent), but the
naming + module shape lines up with the cross-BC factory so a
future second aggregate slots in cleanly.

## Agent-side knobs closed over

  - `stream_type = "Agent"`.
  - `target_id_attr = "agent_id"` -- every Agent transition command
    exposes `agent_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Agent BC.
  - The four codec functions imported from
    `cora.agent.aggregates.agent`.

`extra_log_fields` is a per-slice optional extractor for command-
specific fields the structured log should emit (eg.
`suspend_agent` logs `reason` length so operators searching the
log can find paused agents without dumping the reason text).

## Two factory entry points

`make_agent_update_handler` is the original thin wrapper around
`cora.infrastructure.update_handler.make_update_handler`. Use for
slices whose decider takes only `state` + `command` + `now` (the
fold-NEITHER posture).

`make_agent_actor_update_handler` is the fold-symmetry variant: it
threads the envelope's `principal_id` into the decider under
`actor_kwarg` (e.g. `suspended_by`, `resumed_by`) so the resulting
event payload carries the canonical `<verb>_by` attribution half.
Mirrors `cora.federation._actor_update_handler.make_actor_update_handler`
byte-for-byte modulo the Agent-specific defaults; the body
duplicates `make_update_handler`'s flow because `principal_id` only
enters scope at handler-call time, not at factory-build time.
"""

from collections.abc import Callable, Sequence
from datetime import datetime  # noqa: TC003 (runtime-imported for clarity)
from typing import Any, Protocol
from uuid import UUID

from cora.agent.aggregates.agent import (
    AgentEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.infrastructure.update_handler import make_update_handler
from cora.shared.identity import ActorId

_STREAM_TYPE = "Agent"
_TARGET_ID_ATTR = "agent_id"


def make_agent_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AgentEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Agent slice (fold-NEITHER posture)."""
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
    """Callable shape returned by `make_agent_actor_update_handler`.

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


def make_agent_actor_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AgentEvent]],
    actor_kwarg: str,
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
) -> _ActorUpdateHandler:
    """Build an actor-stamping update handler for one Agent slice.

    `actor_kwarg` is the decider's `<verb>_by` parameter name; the
    handler passes the envelope's `principal_id` (wrapped in `ActorId`)
    under that name on every call. Used by fold-symmetry slices
    (`suspend_agent`, `resume_agent`) whose events carry a folded
    attribution half on the payload.
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
        history: list[AgentEvent] = [from_stored(s) for s in stored]
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


__all__ = ["make_agent_actor_update_handler", "make_agent_update_handler"]
