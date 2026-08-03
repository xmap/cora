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
ONCE duplicated `make_update_handler`'s flow, because `principal_id` enters
scope at handler-call time rather than at factory-build time.

COLLAPSED 2026-08-03: `make_update_handler` takes an optional
`actor_kwarg` and threads the principal itself, so this factory is now a
thin wrapper like its non-stamping sibling and carries no body of its own.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.budget.aggregates.allocation import (
    AllocationEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.budget.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler

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


def make_allocation_actor_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AllocationEvent]],
    actor_kwarg: str,
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Allocation slice, stamping the actor.

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


__all__ = ["make_allocation_actor_update_handler", "make_allocation_update_handler"]
