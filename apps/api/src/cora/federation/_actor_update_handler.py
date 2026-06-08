"""Federation update-handler factory that stamps the invoking actor.

Federation transition events carry an audit denorm (`<verb>_by_actor_id`)
sourced from the request envelope's `principal_id`. The cross-BC
`cora.infrastructure.update_handler.make_update_handler` only threads
`state`, `command`, and `now` into the decider; it cannot pass
`principal_id` because that value only enters scope at handler call
time, not at factory-build time. This module supplies the Federation-
local variant that mirrors the cross-BC body byte-for-byte but adds
the actor-kwarg injection at the decide call.

## Per-aggregate wrappers close over the Federation knobs

`make_permit_update_handler`, `make_credential_update_handler`, and
`make_seal_update_handler` close over each aggregate's codec quartet,
stream type, target-id attribute, and (for Seal) the deterministic
stream-id derivation. Each per-slice `bind(deps)` then supplies the
three per-slice knobs (command_name, log_prefix, decide_fn) plus the
`actor_kwarg` name matching the decider's `<verb>_by_actor_id`
parameter.

## Stream-id derivation

The Seal aggregate is a per-facility singleton: its event-store stream
UUID is derived from `command.facility_id` via `seal_stream_id`
(UUID5), not pulled from a UUID command attribute. The optional
`resolve_stream_id` knob lets Seal slices override the default
`getattr(command, target_id_attr)` while keeping `target_id_attr` as
the log-line field name (so Seal slices log `facility_id=...` as a
str, matching the pre-refactor log shape).

## BC-local, not cross-BC

Federation is the first BC to ship the actor-stamping pattern at the
update-handler boundary. Hoist this factory to
`cora.infrastructure.update_handler` only when a second BC ships the
same shape (rule-of-three discipline). The Calibration
`append_calibration_revision` slice is conceptually similar but is a
non-FSM append with a different command-shape contract; not a clean
second instance.

## Why a separate body (not delegation)

The factory CANNOT delegate to `make_update_handler` because the
decider call needs to include `**{actor_kwarg: principal_id}` and
`principal_id` enters scope per-call, not at factory build. The body
below is a literal copy of `make_update_handler`'s body with one
delta: the decide call appends the actor kwarg. Keep the two bodies
in lockstep when either changes.

## Multi-stream handlers stay longhand

Same carve-out as the cross-BC factory: slices that need to load or
append additional streams (revoke_credential, rotate_seal_online_key,
initialize_seal write a Decision audit stream alongside the aggregate)
cannot use this factory and stay longhand.
"""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.federation.aggregates.credential import (
    CredentialEvent,
)
from cora.federation.aggregates.credential import (
    event_type_name as credential_event_type_name,
)
from cora.federation.aggregates.credential import (
    fold as credential_fold,
)
from cora.federation.aggregates.credential import (
    from_stored as credential_from_stored,
)
from cora.federation.aggregates.credential import (
    to_payload as credential_to_payload,
)
from cora.federation.aggregates.permit import (
    PermitEvent,
)
from cora.federation.aggregates.permit import (
    event_type_name as permit_event_type_name,
)
from cora.federation.aggregates.permit import (
    fold as permit_fold,
)
from cora.federation.aggregates.permit import (
    from_stored as permit_from_stored,
)
from cora.federation.aggregates.permit import (
    to_payload as permit_to_payload,
)
from cora.federation.aggregates.seal import (
    SealEvent,
)
from cora.federation.aggregates.seal import (
    event_type_name as seal_event_type_name,
)
from cora.federation.aggregates.seal import (
    fold as seal_fold,
)
from cora.federation.aggregates.seal import (
    from_stored as seal_from_stored,
)
from cora.federation.aggregates.seal import (
    to_payload as seal_to_payload,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId


class _DomainEvent(Protocol):
    """Structural contract every aggregate's event satisfies.

    Re-declared locally (not imported from
    `cora.infrastructure.update_handler`) so the BC-local factory
    stays free of private cross-package imports.
    """

    @property
    def occurred_at(self) -> datetime: ...


class _ActorUpdateHandler(Protocol):
    """Callable shape returned by the factory.

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


def make_actor_update_handler[TEvent: _DomainEvent](
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
    actor_kwarg: str,
    resolve_stream_id: Callable[[Any], UUID] | None = None,
) -> _ActorUpdateHandler:
    """Build a single-stream actor-stamping update handler.

    `actor_kwarg` is the decider's `<verb>_by_actor_id` parameter
    name; the handler passes the envelope's `principal_id` under that
    name on every call. `resolve_stream_id` overrides the default
    `getattr(command, target_id_attr)` for aggregates whose stream
    UUID is derived (Seal's per-facility singleton); the log-line
    field uses `target_id_attr` regardless.
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
        target_id_value: Any = getattr(command, target_id_attr)
        stream_id: UUID = (
            resolve_stream_id(command) if resolve_stream_id is not None else target_id_value
        )
        log_target_value: Any = (
            target_id_value if isinstance(target_id_value, str) else str(target_id_value)
        )

        log.info(
            f"{log_prefix}.start",
            command_name=command_name,
            **{target_id_attr: log_target_value},
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
                **{target_id_attr: log_target_value},
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise unauthorized_error(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=stream_type,
            stream_id=stream_id,
        )
        history: list[TEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        now: datetime = deps.clock.now()

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
            stream_type=stream_type,
            stream_id=stream_id,
            expected_version=current_version,
            events=new_events,
        )

        log.info(
            f"{log_prefix}.success",
            command_name=command_name,
            **{target_id_attr: log_target_value},
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler


def make_permit_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[PermitEvent]],
    actor_kwarg: str,
) -> _ActorUpdateHandler:
    """Build an actor-stamping handler for one Permit transition slice."""
    return make_actor_update_handler(
        deps,
        stream_type="Permit",
        target_id_attr="permit_id",
        from_stored=permit_from_stored,
        to_payload=permit_to_payload,
        event_type_name=permit_event_type_name,
        fold=permit_fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        actor_kwarg=actor_kwarg,
    )


def make_credential_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[CredentialEvent]],
    actor_kwarg: str,
) -> _ActorUpdateHandler:
    """Build an actor-stamping handler for one Credential transition slice."""
    return make_actor_update_handler(
        deps,
        stream_type="Credential",
        target_id_attr="credential_id",
        from_stored=credential_from_stored,
        to_payload=credential_to_payload,
        event_type_name=credential_event_type_name,
        fold=credential_fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        actor_kwarg=actor_kwarg,
    )


def make_seal_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SealEvent]],
    actor_kwarg: str,
) -> _ActorUpdateHandler:
    """Build an actor-stamping handler for one Seal transition slice.

    Seal slices key the event-store stream by `seal_stream_id(facility_id)`
    (UUID5 over the federation namespace) so the per-facility singleton
    stays addressable from `command.facility_id: str`. The log line
    still reports `facility_id=<str>` (no UUID exposure).
    """
    return make_actor_update_handler(
        deps,
        stream_type="Seal",
        target_id_attr="facility_id",
        from_stored=seal_from_stored,
        to_payload=seal_to_payload,
        event_type_name=seal_event_type_name,
        fold=seal_fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        actor_kwarg=actor_kwarg,
        resolve_stream_id=lambda cmd: seal_stream_id(cmd.facility_id),
    )


__all__ = [
    "make_actor_update_handler",
    "make_credential_update_handler",
    "make_permit_update_handler",
    "make_seal_update_handler",
]
