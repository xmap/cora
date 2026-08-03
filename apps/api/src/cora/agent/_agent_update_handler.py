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
ONCE duplicated `make_update_handler`'s flow, because `principal_id` enters
scope at handler-call time rather than at factory-build time.

COLLAPSED 2026-08-03: `make_update_handler` takes an optional
`actor_kwarg` and threads the principal itself, so this factory is now a
thin wrapper like its non-stamping sibling and carries no body of its own.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.agent.aggregates.agent import (
    AgentEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler

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


def make_agent_actor_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AgentEvent]],
    actor_kwarg: str,
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Agent slice, stamping the actor.

    Delegates to the cross-BC factory. `actor_kwarg` names the decider keyword
    that receives `ActorId(principal_id)`; the core threads it, so this wrapper
    carries no body of its own.
    """
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
        actor_kwarg=actor_kwarg,
        extra_log_fields=extra_log_fields,
    )


__all__ = ["make_agent_actor_update_handler", "make_agent_update_handler"]
