"""Bootstrap-time seed for the AuthorityRevocationHolder Agent (kill-switch K3).

The AuthorityRevocationHolder is a DETERMINISTIC (non-LLM) subscriber: it reacts
to `PolicyGrantRevoked` and holds each in-flight Run the revoked principal drives
(appending RunHeld directly via Pattern C, guarding Running in-process, NOT
calling the hold_run slice, which is off-limits across the tach BC boundary),
recording one `Decision(context=AuthorityRevocationHold)` per run. It needs an
Agent record (and its co-registered Actor) at the pinned
`AUTHORITY_REVOCATION_HOLDER_AGENT_ID` so it can author Decisions
(`decided_by = ActorId(...)`) and hold Runs as an agent-kind principal.

Mirrors `cora.agent.seed_run_supervisor.seed_run_supervisor_agent` verbatim
except for the per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

Per the kill-switch design (K3, [[project-budget-bc-research]] sibling work in
the T-ASE resource-accountability paper's four-gates plan):
  - Pinned UUID in the deployment-controlled `b111` range (a hex-valid nod to
    the kill-switch "block" mnemonic), distinct from every other agent block;
    deployment-stable forever. Changing it orphans every prior holder-authored
    Decision.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a Rule brain
    (`BrainRef.for_rule("AuthorityRevocationHolder:v1")`). The runtime is an
    event-triggered subscriber, not an LLM call. The watch this bullet used to
    carry, that the Agent aggregate was LLM-shaped and wanted a first-class
    deterministic-agent shape if more rule-agents landed, has fired and been
    answered: eighteen landed, and `BrainRef` is that shape.
  - Authorization: the subscriber authorizes HoldRun through the Authorize port
    as its own principal before writing RunHeld. Under the default
    AllowAllAuthorize it is permitted (the bootstrap window: holds are ungated
    until TrustAuthorize is wired); under TrustAuthorize the operator's single
    configured Policy must include this principal + {HoldRun}. Without the grant
    an auto-hold is a logged no-op (Authorize Deny -> HoldDeferred), so the
    kill-switch degrades safe rather than crashing.
  - Not a safety interlock: an auto-hold is a REVERSIBLE wind-down of a software
    principal (resume_run exists), edge-triggered and fail-safe, NOT the floor
    PSS. It sits between WARN and Clearance on the governance rung.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# AuthorityRevocationHolder agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other pinned agent
# ids: changing this orphans every prior holder-authored Decision (their
# actor_id pointers go stale). UUID is in the deployment-controlled `b111` range
# (a hex-valid nod to the kill-switch "block" mnemonic), distinct from every
# other agent block, keeping the bootstrap constants visually grouped per agent.
AUTHORITY_REVOCATION_HOLDER_AGENT_ID = UUID("01900000-0000-7000-8000-0000b1110010")
AUTHORITY_REVOCATION_HOLDER_AGENT_NAME = "AuthorityRevocationHolder"
AUTHORITY_REVOCATION_HOLDER_AGENT_KIND = "AuthorityRevocationHolder"
AUTHORITY_REVOCATION_HOLDER_AGENT_VERSION = "1.0.0"
AUTHORITY_REVOCATION_HOLDER_AGENT_DESCRIPTION = (
    "Deterministic kill-switch subscriber: on a PolicyGrantRevoked, holds each "
    "in-flight Run the revoked principal drives (Running only) and records one "
    "Decision(context=AuthorityRevocationHold) per run. A "
    "reversible, fail-safe wind-down of a software principal, not a safety "
    "interlock (the floor PSS owns hard safety)."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000b1110012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000b1110013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000b1110014")


async def seed_authority_revocation_holder_agent(kernel: Kernel) -> None:
    """Seed the AuthorityRevocationHolder Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
        name=AUTHORITY_REVOCATION_HOLDER_AGENT_NAME,
        kind=AUTHORITY_REVOCATION_HOLDER_AGENT_KIND,
        version=AUTHORITY_REVOCATION_HOLDER_AGENT_VERSION,
        description=AUTHORITY_REVOCATION_HOLDER_AGENT_DESCRIPTION,
        brain=BrainRef.for_rule("AuthorityRevocationHolder:v1"),
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedAuthorityRevocationHolderAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "AUTHORITY_REVOCATION_HOLDER_AGENT_DESCRIPTION",
    "AUTHORITY_REVOCATION_HOLDER_AGENT_ID",
    "AUTHORITY_REVOCATION_HOLDER_AGENT_KIND",
    "AUTHORITY_REVOCATION_HOLDER_AGENT_NAME",
    "AUTHORITY_REVOCATION_HOLDER_AGENT_VERSION",
    "seed_authority_revocation_holder_agent",
]
