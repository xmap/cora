"""Application handler for the `define_agent` slice.

Cross-BC atomic genesis: writes `ActorRegistered(kind="agent")` on
the Access BC stream AND `AgentDefined` on the Agent BC stream in
ONE Postgres transaction via `EventStore.append_streams`. Mirrors
11a-c-2 `amend_clearance` and 11b-a `supersede_caution` cross-
aggregate atomic-write patterns; the new wrinkle is that the two
streams belong to DIFFERENT BCs (Access + Agent).

The shared `agent_id == actor_id` is generated once by the handler
and used on both events. `Decision.actor_id` cross-BC references
work uniformly because every Agent's id is registered as an Actor
in the same transaction; no polymorphism, no saga compensation.

Per the design lock: the decider builds only the Agent BC event
(`AgentDefined`); this handler additionally builds the Access BC
event (`ActorRegistered(kind="agent")`) and threads both into the
single `append_streams` call.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

Catalog gate: after validation and before any write, the handler
resolves the command's model identity via
`deps.language_model_lookup` and refuses with
`LanguageModelNotApprovedError` unless the entry is Approved. The
kernel's default lookup approves everything, so the gate arms only
when a deployment stands up a real catalog.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
    ProfileStore,
)
from cora.access.aggregates.actor import (
    event_type_name as actor_event_type_name,
)
from cora.access.aggregates.actor import (
    to_payload as actor_to_payload,
)
from cora.agent.aggregates.agent import AgentName, event_type_name, to_payload
from cora.agent.aggregates.language_model import (
    LanguageModelNotApprovedError,
    LanguageModelStatus,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID

_AGENT_STREAM_TYPE = "Agent"
_ACTOR_STREAM_TYPE = "Actor"
_COMMAND_NAME = "DefineAgent"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_agent handler -- what `bind()` returns.

    Returns the new agent's UUID (also the new Actor's UUID; same
    value). Has no idempotency_key kwarg; `with_idempotency` at
    wire.py adds it.
    """

    async def __call__(
        self,
        command: DefineAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_agent handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel, *, profile_store: ProfileStore) -> Handler:
    """Build a define_agent handler closed over the shared deps.

    `profile_store` is the Access BC PII vault adapter; the cross-BC
    atomic write upserts the display name into `actor_profile` BEFORE
    appending both event streams. Order rationale: the profile upsert
    is idempotent on actor_id PK (a retry replays cleanly), so writing
    it first means that if append_streams fails the worst case is an
    orphan profile row tied to an `actor_id` that never got an event.
    The reverse order would risk leaving an Agent + Actor in the event
    log with no display name — and `load_actor_display_name` would
    surface the tombstone for a freshly-defined agent, which is a
    surprising UX.
    """

    async def handler(
        command: DefineAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_agent.start",
            command_name=_COMMAND_NAME,
            kind=command.kind,
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
                "define_agent.denied",
                command_name=_COMMAND_NAME,
                kind=command.kind,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        # Build the Agent BC event via the pure decider.
        agent_domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
        )

        # Build the Access BC co-write event directly in the handler.
        # Per the PII vault pattern the event carries no display name;
        # the name lands in `actor_profile` via profile_store.upsert
        # below. Route the validated name through `AgentName(...)` (the
        # same VO the decider used) so both the upsert and any future
        # diagnostic surface see one canonical trimmed value.
        validated_name = AgentName(command.name).value
        actor_event = ActorRegistered(
            actor_id=new_id,
            occurred_at=now,
            kind=ActorKind.AGENT,
        )

        # Catalog gate: the declared model identity must hold an
        # Approved catalog entry. Runs BEFORE the vault upsert and the
        # append so a refused registration leaves no orphan profile row.
        entry = await deps.language_model_lookup.find_by_model(
            provider=command.model_ref.provider,
            model=command.model_ref.model,
        )
        if entry is None or entry.status != LanguageModelStatus.APPROVED.value:
            raise LanguageModelNotApprovedError(
                command.model_ref.provider,
                command.model_ref.model,
                entry.status if entry is not None else None,
            )

        agent_new_events = [
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
            for event in agent_domain_events
        ]
        actor_new_events = [
            to_new_event(
                event_type=actor_event_type_name(actor_event),
                payload=actor_to_payload(actor_event),
                occurred_at=actor_event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
        ]

        # Vault upsert FIRST per the order rationale in `bind`. If
        # this fails the caller retries the whole command and the
        # idempotent upsert + version-0 append both replay cleanly.
        await profile_store.upsert(
            actor_id=new_id,
            name=validated_name,
            created_at=now,
        )

        await deps.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_ACTOR_STREAM_TYPE,
                    stream_id=new_id,
                    expected_version=0,
                    events=actor_new_events,
                ),
                StreamAppend(
                    stream_type=_AGENT_STREAM_TYPE,
                    stream_id=new_id,
                    expected_version=0,
                    events=agent_new_events,
                ),
            ]
        )

        _log.info(
            "define_agent.success",
            command_name=_COMMAND_NAME,
            kind=command.kind,
            agent_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            agent_event_count=len(agent_new_events),
            actor_event_count=len(actor_new_events),
        )
        return new_id

    return handler
