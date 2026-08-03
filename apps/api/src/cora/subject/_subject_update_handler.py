"""Subject BC's update-handler factory (thin wrapper + actor-stamping variant).

Closes over Subject-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

Cross-BC hoist landed once Recipe and Run shipped a combined 11
byte-identical longhand handlers; the trigger documented at this
file's earlier longhand body had fired. Slice call sites
(`make_subject_update_handler(...)`) are unchanged across the hoist.

## Subject-side knobs closed over

  - `stream_type = "Subject"`.
  - `target_id_attr = "subject_id"` -- every Subject update
    command exposes `subject_id: UUID`. If a future Subject
    command needs a differently-named target field, the slice
    cannot use this factory and must stay longhand.
  - `unauthorized_error = UnauthorizedError` from the Subject BC.
  - The four codec functions imported from
    `cora.subject.aggregates.subject`.

Per-slice inputs (`command_name`, `log_prefix`, `decide_fn`, plus
the optional `extra_log_fields` extractor) pass straight through
to `make_update_handler`. Subject's existing slices (Mount /
Measure / Remove / Return / Store / Discard / Dismount) carry
only `subject_id` in their log lines, so none of them currently
pass `extra_log_fields`.

## Two factory entry points

`make_subject_update_handler` is the original thin wrapper around
`cora.infrastructure.update_handler.make_update_handler`. Use for
slices whose decider takes only `state` + `command` + `now` (the
pre-fold-symmetry shape; no Subject slice uses this any more, but
the entry point stays for future slices that opt out).

`make_subject_actor_update_handler` is the fold-symmetry variant:
it threads the envelope's `principal_id` into the decider under
`actor_kwarg` (for example `measured_by`, `removed_by`, `discarded_by`)
so the resulting event payload carries the canonical `<verb>_by`
attribution half. Mirrors
`cora.agent._agent_update_handler.make_agent_actor_update_handler`
byte-for-byte modulo the Subject-specific defaults; the body
ONCE duplicated `make_update_handler`'s flow, because `principal_id` enters
scope at handler-call time rather than at factory-build time.

COLLAPSED 2026-08-03: `make_update_handler` takes an optional
`actor_kwarg` and threads the principal itself, so this factory is now a
thin wrapper like its non-stamping sibling and carries no body of its own.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.subject.aggregates.subject import (
    SubjectEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.subject.errors import UnauthorizedError

_STREAM_TYPE = "Subject"
_TARGET_ID_ATTR = "subject_id"


def make_subject_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SubjectEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Subject slice (no actor stamping)."""
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


def make_subject_actor_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SubjectEvent]],
    actor_kwarg: str,
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Subject slice, stamping the actor.

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


__all__ = ["make_subject_actor_update_handler", "make_subject_update_handler"]
