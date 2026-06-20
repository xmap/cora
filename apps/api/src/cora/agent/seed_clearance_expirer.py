"""Bootstrap-time seed for the ClearanceExpirer Agent.

The ClearanceExpirer runtime (CORA's 3rd ACTIVE agent, a composition-root
periodic loop) needs an Agent record (and its co-registered Actor) at the
pinned `CLEARANCE_EXPIRER_AGENT_ID` so it can author ClearanceExpiry
Decisions (`decided_by = ActorId(CLEARANCE_EXPIRER_AGENT_ID)`) and issue
`expire_clearance` as an agent-kind principal. Mirrors
`cora.agent.seed_run_supervisor` except for the per-agent constants; the
shared scaffolding lives in `cora.agent._agent_seed`.

Per [[project-clearance-window-expirer-design]]:
  - Pinned UUID in the `eeee00XX` range (fifth seeded identity, sibling to
    RunDebriefer `aaaa00XX`, CautionDrafter `bbbb00XX`, RunSupervisor
    `cccc00XX`, CautionPromoter `dddd00XX`); deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`), never used to build an LLM (the runtime
    is a periodic loop applying a clock comparison).
  - Authorization: the runtime issues `expire_clearance` through the
    Authorize port like any principal. Under the default AllowAllAuthorize
    it is permitted; under TrustAuthorize the operator's single configured
    Policy must include this principal + {ExpireClearance}. No separate
    Policy is seeded: TrustAuthorize evaluates exactly ONE configured
    policy, so a separate ClearanceExpirer policy would never be consulted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# ClearanceExpirer agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other seeded
# agents: changing this orphans every prior ClearanceExpirer-authored
# Decision (their actor_id pointers go stale). UUID is in the
# deployment-controlled `eeee00XX` range (fifth seeded identity).
CLEARANCE_EXPIRER_AGENT_ID = UUID("01900000-0000-7000-8000-0000eeee0010")
CLEARANCE_EXPIRER_AGENT_NAME = "ClearanceExpirer"
CLEARANCE_EXPIRER_AGENT_KIND = "ClearanceExpirer"
CLEARANCE_EXPIRER_AGENT_VERSION = "1.0.0"
CLEARANCE_EXPIRER_AGENT_DESCRIPTION = (
    "Deterministic in-loop agent: expires Active safety Clearances whose "
    "validity window (valid_until) has elapsed, issuing expire_clearance and "
    "recording one Decision(context=ClearanceExpiry) per expiry. Wind-down "
    "only (removes a stale authorization); never a safety interlock."
)


# Sentinel model ref: ClearanceExpirer is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build an
# LLM (the runtime is a periodic clock comparison, no build_llm call).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:ClearanceExpirer:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000eeee0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000eeee0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000eeee0014")


async def seed_clearance_expirer_agent(kernel: Kernel) -> None:
    """Seed the ClearanceExpirer Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CLEARANCE_EXPIRER_AGENT_ID,
        name=CLEARANCE_EXPIRER_AGENT_NAME,
        kind=CLEARANCE_EXPIRER_AGENT_KIND,
        version=CLEARANCE_EXPIRER_AGENT_VERSION,
        description=CLEARANCE_EXPIRER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedClearanceExpirerAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CLEARANCE_EXPIRER_AGENT_DESCRIPTION",
    "CLEARANCE_EXPIRER_AGENT_ID",
    "CLEARANCE_EXPIRER_AGENT_KIND",
    "CLEARANCE_EXPIRER_AGENT_NAME",
    "CLEARANCE_EXPIRER_AGENT_VERSION",
    "seed_clearance_expirer_agent",
]
