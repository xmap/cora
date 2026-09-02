"""Whether the shipped fleet can actually act, as a value and as a verdict.

`_seeded_fleet` made the fleet a value so a gesture could be made over
it. This asks the question that value exists for, and says the answer out
loud at boot.

## Why this is a warning and not a metric

A `Defined` Agent is registered and inert: the subscribers' lifecycle
gate fires on `Versioned` only, and refuses anything less WITHOUT
SAYING SO. On the 2-BM pilot that stranded seventeen agents for three
months behind a log that looked clean the entire time. The remedy
(`promote_seeded_fleet`) has existed since; what did not exist was
anything that told an operator the remedy was needed.

So the point here is not the number. It is that a deployment whose fleet
cannot act now says so on every boot, at `warning`, naming the members.
An absence has to be its own loud verdict, because the alternative is
what already happened: a correct system, a clean log, and nothing
running.

## Four not-ready reasons, kept apart

They are not interchangeable and collapsing them would restore the
silence at one remove:

  `not_ready`  `Defined`. Never promoted. THE silent case, and the only
               one this treats as a fault, because it is the only one
               nobody chose.
  `held`       `Suspended`. A live operator decision. Reported, never
               warned about; a deployment pausing an agent on purpose
               should not be nagged for it.
  `retired`    `Deprecated`. Terminal and deliberate.
  `absent`     Not in the record at all. Worth seeing on a partly-seeded
               deployment rather than counting as a silent zero, the same
               reasoning `promote_seeded_fleet` applies to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.agent._seeded_fleet import SEEDED_FLEET
from cora.agent.aggregates.agent import AgentStatus, load_agent
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from uuid import UUID

    from cora.agent._seeded_fleet import SeededAgent
    from cora.infrastructure.ports import EventStore

_log = get_logger(__name__)


@dataclass(frozen=True)
class FleetReadiness:
    """Fleet members by whether they can act, named rather than counted.

    Names and not ids: this is read by an operator deciding whether to
    run a promotion, and `RunWitness` answers that question where
    `01900000-0000-7000-8000-0000aaaa0010` does not. The ids stay
    reachable through `SEEDED_FLEET` for anything that needs to act on a
    member.
    """

    ready: tuple[str, ...]
    not_ready: tuple[str, ...]
    held: tuple[str, ...]
    retired: tuple[str, ...]
    absent: tuple[str, ...]

    @property
    def total(self) -> int:
        return (
            len(self.ready)
            + len(self.not_ready)
            + len(self.held)
            + len(self.retired)
            + len(self.absent)
        )

    @property
    def stranded(self) -> bool:
        """Whether any member is inert for a reason nobody chose."""
        return bool(self.not_ready)


def fleet_readiness(
    statuses: Mapping[UUID, AgentStatus | None],
    fleet: Sequence[SeededAgent] = SEEDED_FLEET,
) -> FleetReadiness:
    """Sort the fleet by readiness. Pure, so the unit tier drives every
    branch without a record.

    Ranges over `fleet`, never over `statuses`: a member the caller
    failed to look up has to land in `absent`, and a map missing that key
    would otherwise drop it from the count entirely. The total is then a
    property of the shipped fleet, which is the only thing that makes
    "4 of 20" mean anything.
    """
    buckets: dict[str, list[str]] = {
        "ready": [],
        "not_ready": [],
        "held": [],
        "retired": [],
        "absent": [],
    }
    for member in fleet:
        match statuses.get(member.agent_id):
            case AgentStatus.VERSIONED:
                buckets["ready"].append(member.name)
            case AgentStatus.DEFINED:
                buckets["not_ready"].append(member.name)
            case AgentStatus.SUSPENDED:
                buckets["held"].append(member.name)
            case AgentStatus.DEPRECATED:
                buckets["retired"].append(member.name)
            case None:
                buckets["absent"].append(member.name)
    return FleetReadiness(
        ready=tuple(buckets["ready"]),
        not_ready=tuple(buckets["not_ready"]),
        held=tuple(buckets["held"]),
        retired=tuple(buckets["retired"]),
        absent=tuple(buckets["absent"]),
    )


async def read_fleet_readiness(event_store: EventStore) -> FleetReadiness:
    """Load every shipped member and sort it. Read-only."""
    statuses: dict[UUID, AgentStatus | None] = {}
    for member in SEEDED_FLEET:
        agent = await load_agent(event_store, member.agent_id)
        statuses[member.agent_id] = None if agent is None else agent.status
    return fleet_readiness(statuses)


def log_fleet_readiness(readiness: FleetReadiness) -> None:
    """Say it out loud, at a level that matches whether anything is wrong.

    `warning` when a member is stranded, because that is a deployment
    that will quietly do nothing, and the whole reason this function
    exists is that the previous behaviour was indistinguishable from a
    healthy boot. `info` otherwise: a fleet nobody needs to act on should
    not train an operator to scroll past this line.
    """
    if readiness.stranded:
        _log.warning(
            "agent_fleet.stranded",
            ready=len(readiness.ready),
            total=readiness.total,
            not_ready=list(readiness.not_ready),
            remedy="promote_seeded_fleet",
        )
    else:
        _log.info("agent_fleet.ready", ready=len(readiness.ready), total=readiness.total)
    if readiness.absent:
        _log.warning("agent_fleet.absent", absent=list(readiness.absent))


__all__ = [
    "FleetReadiness",
    "fleet_readiness",
    "log_fleet_readiness",
    "read_fleet_readiness",
]
