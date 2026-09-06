"""Bootstrap-time seed for the StatusPublisher Agent.

The StatusPublisher identity backs the external status page relay
(`cora.api._status_push`): a runtime that pushes a live snapshot of the
facility over a websocket to an external relay, since the 2-BM pilot has
no inbound reachability for a dashboard to pull from directly. Mirrors
`cora.agent.seed_run_witness.seed_run_witness_agent` verbatim except for
the per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

  - Pinned UUID continues the numeric-mnemonic range at `4444`, the next
    unclaimed block after `3333` (CaptureProgressFeeder); deployment-stable
    forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a Rule brain
    (`BrainRef.for_rule("StatusPublisher:v1")`). Never used to build an LLM: the runtime
    is a read-and-relay loop, not an LLM subscriber.
  - Authorization: `_status_push.py` reads across nine BCs to assemble the
    snapshot it relays: `ListPlans` (Recipe), `ListRuns` and
    `GetRunHistory` (Run), `ListSubjects` (Subject), `ListCampaigns`
    (Campaign), `ListDatasets` (Data), `ListProcedures` (Operation),
    `ListClearances` (Safety), `ListEnclosures` and `GetEnclosureHistory`
    (Enclosure), and `ListDecisions` (Decision). This identity only seeds
    the Agent record; `_status_push.py` still issues every one of those
    reads as `SYSTEM_PRINCIPAL_ID` and does not yet act as this agent.
    Switching it over, and granting this principal the eleven commands
    above under a real `TrustAuthorize` Policy, is separate follow-up
    work, not part of this seed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# StatusPublisher agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_WITNESS_AGENT_ID`: changing this orphans every prior
# StatusPublisher-authored read's principal_id pointer once one exists.
# UUID opens a new numeric block at `4444` (next unclaimed after `3333`).
STATUS_PUBLISHER_AGENT_ID = UUID("01900000-0000-7000-8000-000044440010")
STATUS_PUBLISHER_AGENT_NAME = "StatusPublisher"
STATUS_PUBLISHER_AGENT_KIND = "StatusPublisher"
STATUS_PUBLISHER_AGENT_VERSION = "1.0.0"
STATUS_PUBLISHER_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: reads a live snapshot across the "
    "Recipe, Run, Subject, Campaign, Data, Operation, Safety, Enclosure, "
    "and Decision BCs and pushes it over a websocket to an external "
    "status-page relay. Not a control path: it never issues a write "
    "command, only reads and relays."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000044440012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000044440013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000044440014")


async def seed_status_publisher_agent(kernel: Kernel) -> None:
    """Seed the StatusPublisher Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=STATUS_PUBLISHER_AGENT_ID,
        name=STATUS_PUBLISHER_AGENT_NAME,
        kind=STATUS_PUBLISHER_AGENT_KIND,
        version=STATUS_PUBLISHER_AGENT_VERSION,
        description=STATUS_PUBLISHER_AGENT_DESCRIPTION,
        brain=BrainRef.for_rule("StatusPublisher:v1"),
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedStatusPublisherAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "STATUS_PUBLISHER_AGENT_DESCRIPTION",
    "STATUS_PUBLISHER_AGENT_ID",
    "STATUS_PUBLISHER_AGENT_KIND",
    "STATUS_PUBLISHER_AGENT_NAME",
    "STATUS_PUBLISHER_AGENT_VERSION",
    "seed_status_publisher_agent",
]
