"""Promote a deployment's shipped fleet from Defined to Versioned.

A one-time operator gesture for a deployment seeded before the
bootstrap promoted. `Defined` means registered as config but not ready
for invocation, so a fleet stuck there cannot act, and the subscribers
that refuse it say nothing when they do. On the 2-BM pilot that was
seventeen agents inert for three months with a clean-looking log.

The seed will not fix this on restart, deliberately: appending
governance events to a record that has no edit path should be something
a person chose. This is how they choose it.

## Why an entrypoint and not a feature slice

It was written as a slice first, and the architecture tests were right
to reject it. A slice is one command against one aggregate, with a
decider and an MCP tool; this is a maintenance fan-out across seventeen
aggregates with no decision of its own to make. Forcing it into that
mould meant either duplicating `version_agent`'s promotion rule or
importing across slices, both of which the fitness functions forbid for
good reason.

So it takes the shape `record_export.export_bundle` already uses: a
plain async function an operator invokes against a live deployment,
outside the request surfaces. It also keeps promotion off MCP, which
matters because promotion is what grants an Agent authority to act, and
an agent able to call it could grant that to itself.

## Semantics

Per-agent rather than atomic: the promotions are independent, a partial
run is safe to re-run, and one unrelated conflict should not roll back
sixteen good promotions. Idempotent: a second run reports the earlier
ones as already ready and writes nothing.

`Suspended` and `Deprecated` members are reported, never promoted.
Suspension is a live operator decision this must not quietly reverse,
and deprecation is terminal. An absent member is reported too, since on
a partly-seeded deployment that is worth seeing rather than counting as
a silent zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.agent._seeded_fleet import SEEDED_FLEET
from cora.agent.aggregates.agent import AgentStatus, load_agent
from cora.agent.features.version_agent import VersionAgent
from cora.agent.features.version_agent import bind as bind_version_agent
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import SYSTEM_IN_PROCESS_SURFACE_ID

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel

_log = get_logger(__name__)

OUTCOME_PROMOTED = "promoted"
OUTCOME_ALREADY_READY = "already_ready"
OUTCOME_ABSENT = "absent"
OUTCOME_SKIPPED = "skipped"


@dataclass(frozen=True)
class FleetMemberOutcome:
    """What the promotion did about one fleet member."""

    agent_id: UUID
    name: str
    status_before: str | None
    outcome: str


@dataclass(frozen=True)
class PromotionSummary:
    """What the promotion did about the fleet, member by member.

    Every member is reported, not only the changed ones: a count of
    promotions cannot tell an operator what it passed over, and passing
    something over silently is the failure this whole exercise exists to
    stop repeating.
    """

    dry_run: bool
    outcomes: tuple[FleetMemberOutcome, ...]

    def count(self, outcome: str) -> int:
        return sum(1 for item in self.outcomes if item.outcome == outcome)


async def promote_seeded_fleet(
    kernel: Kernel,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    dry_run: bool = False,
) -> PromotionSummary:
    """Promote every Defined fleet member; report on all of them.

    `dry_run` reports the identical summary and writes nothing, so an
    operator can see what a live run would touch before it touches a
    record that cannot be edited afterwards.
    """
    version_agent = bind_version_agent(kernel)
    outcomes: list[FleetMemberOutcome] = []

    for member in SEEDED_FLEET:
        agent = await load_agent(kernel.event_store, member.agent_id)
        if agent is None:
            outcomes.append(FleetMemberOutcome(member.agent_id, member.name, None, OUTCOME_ABSENT))
            continue
        before = agent.status
        if before is AgentStatus.VERSIONED:
            outcome = OUTCOME_ALREADY_READY
        elif before is AgentStatus.DEFINED:
            if not dry_run:
                await version_agent(
                    VersionAgent(agent_id=member.agent_id),
                    principal_id=principal_id,
                    correlation_id=correlation_id,
                    surface_id=SYSTEM_IN_PROCESS_SURFACE_ID,
                )
            outcome = OUTCOME_PROMOTED
        else:
            outcome = OUTCOME_SKIPPED
        outcomes.append(FleetMemberOutcome(member.agent_id, member.name, before.value, outcome))

    summary = PromotionSummary(dry_run=dry_run, outcomes=tuple(outcomes))
    _log.info(
        "promote_seeded_fleet.completed",
        dry_run=dry_run,
        promoted=summary.count(OUTCOME_PROMOTED),
        already_ready=summary.count(OUTCOME_ALREADY_READY),
        skipped=summary.count(OUTCOME_SKIPPED),
        absent=summary.count(OUTCOME_ABSENT),
    )
    return summary


__all__ = [
    "OUTCOME_ABSENT",
    "OUTCOME_ALREADY_READY",
    "OUTCOME_PROMOTED",
    "OUTCOME_SKIPPED",
    "FleetMemberOutcome",
    "PromotionSummary",
    "promote_seeded_fleet",
]
