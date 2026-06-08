"""Cross-BC scaffolding for single-stream update-style handlers.

Hoisted once Recipe and Run shipped a combined 11 longhand
handlers byte-identical to Subject's and Equipment's factored
`make_*_update_handler` shapes. The trigger documented at the
former `cora/equipment/_asset_update_handler.py` (defer to a third
cross-BC instance, point at which the `to_new_event` cleanup
precedent applies) had fired.

## Per-BC wrappers close over the BC-specific knobs

Each BC keeps its own `make_<aggregate>_update_handler` thin
wrapper that supplies:

  - `stream_type` — the event-store stream type, for example `"Subject"`.
  - `target_id_attr` — the command attribute carrying the target
    aggregate id, for example `"subject_id"`. Used both for the
    event-store load key and for the log-line field name (so the
    aggregate's id keeps its semantic name in log search).
  - The four codec functions (`from_stored`, `to_payload`,
    `event_type_name`, `fold`) imported from the aggregate
    package.
  - The BC-local `UnauthorizedError` class — kept per-BC so log
    search distinguishes which BC denied a command, mirroring the
    per-BC error-class convention used elsewhere.

The wrapper's signature stays identical to the pre-hoist
per-aggregate factories, so existing call sites (Subject's six,
Asset's eight-plus) compile unchanged.

## Per-slice inputs

  - `command_name: str` — canonical PascalCase command name.
  - `log_prefix: str` — slice name used for log-line prefixes
    (for example `mount_subject` -> `mount_subject.start` / `.denied` /
    `.success`).
  - `decide_fn: Callable[..., Sequence[TEvent]]` — the slice's
    pure decider.
  - `extra_log_fields: Callable[[Any], dict[str, Any]] | None` —
    OPTIONAL extractor for log fields beyond the target id (for example,
    `version_tag` on `version_method` / `version_practice` /
    `version_plan`, or `schema_present` on
    `update_method_parameters_schema`). Returned dict is merged
    into `start`, `denied`, and `success` log lines. None (the
    default) means no extras and matches the
    pure-single-id-only behaviour of the original Subject /
    Equipment factories.

The `reason` from `Deny` decisions and the `event_count` /
`new_version` on success lines are appended AFTER `extras` so the
log shape stays stable across slices regardless of extras.

## Why a free function (not a base class)

Same rationale documented at `cora.shared.bounded_text`
and `cora.infrastructure.evolver`: a free function lets each per-
BC wrapper bind its own narrow `Handler` Protocol around the
shared body without dragging the cross-BC abstraction into the
type lattice of every aggregate.

## Why `command: Any` at the cross-BC core

Per-BC wrappers can keep their own `_<Aggregate>TargetingCommand`
Protocol if they want narrower typing at the wrapper boundary;
the cross-BC body uses `getattr(command, target_id_attr)` because
the targeting attribute name varies per aggregate. Type narrowing
happens at the slice boundary through each slice's local
`Handler` Protocol, which is contravariant in `command`.

## Multi-stream handlers stay longhand

This factory loads exactly one event-store stream. Slices that
need to load additional streams (for example,
`update_plan_default_parameters` reads Plan + Method to surface
the parameters_schema) cannot use this factory and stay longhand.
"""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID


class _DomainEvent(Protocol):
    """Structural contract every aggregate's event satisfies.

    Every CORA event dataclass carries a payload-captured
    `occurred_at: datetime` (per the non-determinism principle),
    so the cross-BC factory can read it generically.
    """

    @property
    def occurred_at(self) -> datetime: ...


class _UpdateHandler(Protocol):
    """The factory's return shape.

    Each slice's locally-declared `Handler` Protocol is narrower
    in `command` (which is contravariant), so the wider callable
    returned here assigns to it without an explicit cast.

    `surface_id`: additive with nil default so routes that don't
    pass it yet keep working. Routes that have been swept to inject
    the real `Depends(get_surface_id)` value pass it; handlers
    forward whatever they receive to `deps.authz.authorize`.
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


def make_update_handler[TEvent: _DomainEvent](
    deps: Kernel,
    *,
    stream_type: str,
    target_id_attr: str,
    from_stored: Callable[[Any], TEvent],
    to_payload: Callable[[TEvent], dict[str, Any]],
    event_type_name: Callable[[TEvent], str],
    fold: Callable[[list[TEvent]], Any],
    unauthorized_error: type[Exception],
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[TEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
) -> _UpdateHandler:
    """Build a single-stream update handler for one slice.

    See module docstring for the per-BC wrapper pattern.
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
        target_id: UUID = getattr(command, target_id_attr)
        extras: dict[str, Any] = extra_log_fields(command) if extra_log_fields is not None else {}

        log.info(
            f"{log_prefix}.start",
            command_name=command_name,
            **{target_id_attr: str(target_id)},
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
                **{target_id_attr: str(target_id)},
                **extras,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise unauthorized_error(decision.reason)

        now: datetime = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=stream_type,
            stream_id=target_id,
        )
        history: list[TEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide_fn(state=state, command=command, now=now)

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
            stream_type=stream_type,
            stream_id=target_id,
            expected_version=current_version,
            events=new_events,
        )

        log.info(
            f"{log_prefix}.success",
            command_name=command_name,
            **{target_id_attr: str(target_id)},
            **extras,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler


__all__ = ["make_update_handler"]
