"""Shared seed factory for singleton-per-deployment Agent bootstraps.

Both `seed.py` (RunDebriefer) and `seed_caution_drafter.py`
(CautionDrafter) share an identical scaffolding: build the
`AgentDefined` + `ActorRegistered` envelope pair, upsert the PII
vault display name, write atomically via
`event_store.append_streams` with `expected_version=0` on BOTH
streams, and treat `ConcurrencyError` as a no-op for restart
idempotency. Only the per-agent identity constants differ.

This module hoists the shared body into `seed_agent(kernel, identity)`
after the rule of three (RunDebriefer + CautionDrafter; third agent
ships into the same factory unchanged).

The per-agent constants stay in their respective modules so the
deployment-stable identity values remain grouped per agent (matches
the prior convention).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.agent.aggregates.agent import (
    AgentDefined,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentVersion,
    ModelRef,
    event_type_name,
    to_payload,
)
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel


_log = get_logger(__name__)


@dataclass(frozen=True)
class AgentSeedIdentity:
    """Per-agent constants threaded through `seed_agent`.

    Every singleton-agent's `seed_<name>_agent(kernel)` wrapper
    instantiates one of these from the constants declared at its
    own module top-level (so the values remain visible grouped per
    agent), then passes it into the shared factory.
    """

    agent_id: UUID
    name: str
    kind: str
    version: str
    description: str
    model_ref: ModelRef
    prompt_template_id: UUID | None
    agent_event_id: UUID
    actor_event_id: UUID
    correlation_id: UUID
    command_name: str


async def seed_agent(kernel: Kernel, identity: AgentSeedIdentity) -> None:
    """Seed an Agent + co-registered Actor (idempotent).

    No-op if the agent is already seeded; logs the outcome either
    way. Safe to call on every app boot.
    """
    from cora.infrastructure.event_envelope import to_new_event

    now = kernel.clock.now()

    # Validate the constants by routing them through the same VOs
    # the decider uses. If a constant is invalid (eg. too long) we
    # crash at startup with a clear error.
    name = AgentName(identity.name)
    kind = AgentKind(identity.kind)
    version = AgentVersion(identity.version)
    description = AgentDescription(identity.description)

    agent_event = AgentDefined(
        agent_id=identity.agent_id,
        kind=kind.value,
        name=name.value,
        version=version.value,
        model_ref=identity.model_ref,
        description=description.value,
        canonical_uri=None,
        prompt_template_id=identity.prompt_template_id,
        capabilities=frozenset(),
        occurred_at=now,
    )
    actor_event = ActorRegistered(
        actor_id=identity.agent_id,
        occurred_at=now,
        kind=ActorKind.AGENT,
    )

    # PII vault upsert (idempotent on actor_id PK). Pre-append so a
    # ConcurrencyError on the second boot still leaves the profile
    # row in place; pre-append on the FIRST boot establishes the
    # display name before any read path could observe a tombstone.
    await kernel.profile_store.upsert(
        actor_id=identity.agent_id,
        name=name.value,
        created_at=now,
    )

    agent_new_event = to_new_event(
        event_type=event_type_name(agent_event),
        payload=to_payload(agent_event),
        occurred_at=now,
        event_id=identity.agent_event_id,
        command_name=identity.command_name,
        correlation_id=identity.correlation_id,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )
    actor_new_event = to_new_event(
        event_type=actor_event_type_name(actor_event),
        payload=actor_to_payload(actor_event),
        occurred_at=now,
        event_id=identity.actor_event_id,
        command_name=identity.command_name,
        correlation_id=identity.correlation_id,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )

    try:
        await kernel.event_store.append_streams(
            [
                StreamAppend(
                    stream_type="Actor",
                    stream_id=identity.agent_id,
                    expected_version=0,
                    events=[actor_new_event],
                ),
                StreamAppend(
                    stream_type="Agent",
                    stream_id=identity.agent_id,
                    expected_version=0,
                    events=[agent_new_event],
                ),
            ]
        )
    except ConcurrencyError:
        _log.info(
            "agent_seed.already_present",
            agent_id=str(identity.agent_id),
            agent_name=identity.name,
        )
        return

    _log.info(
        "agent_seed.created",
        agent_id=str(identity.agent_id),
        agent_name=identity.name,
        kind=kind.value,
        version=version.value,
    )
