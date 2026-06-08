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
duplicates `make_update_handler`'s flow because `principal_id` only
enters scope at handler-call time, not at factory-build time.
"""

from collections.abc import Callable, Sequence
from datetime import datetime  # noqa: TC003 (runtime-imported for clarity)
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.infrastructure.update_handler import make_update_handler
from cora.shared.identity import ActorId
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


class _ActorUpdateHandler(Protocol):
    """Callable shape returned by `make_subject_actor_update_handler`.

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


def make_subject_actor_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SubjectEvent]],
    actor_kwarg: str,
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
) -> _ActorUpdateHandler:
    """Build an actor-stamping update handler for one Subject slice.

    `actor_kwarg` is the decider's `<verb>_by` parameter name; the
    handler passes the envelope's `principal_id` (wrapped in `ActorId`)
    under that name on every call. Used by fold-symmetry slices
    (`measure_subject`, `remove_subject`, `dismount_subject`,
    `return_subject`, `store_subject`, `discard_subject`) whose events
    carry an attribution half on the payload.
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
        history: list[SubjectEvent] = [from_stored(s) for s in stored]
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


__all__ = ["make_subject_actor_update_handler", "make_subject_update_handler"]
