"""Bootstrap-time seed for the CautionPromoter Agent.

The CautionPromoter subscriber (CORA's 2nd ACTIVE agent) needs an Agent
record (and its co-registered Actor) at the pinned
`CAUTION_PROMOTER_AGENT_ID` so it can author CautionPromotion Decisions
(`decided_by = ActorId(CAUTION_PROMOTER_AGENT_ID)`) and register live
Cautions (`authored_by = ...`) as an agent-kind principal. Mirrors
`cora.agent.seed_run_supervisor` except for the per-agent constants; the
shared scaffolding lives in `cora.agent._agent_seed`.

Per [[project-caution-promoter-design]]:
  - Pinned UUID in the `dddd00XX` range (fourth agent, sibling to the
    RunDebriefer `aaaa00XX`, CautionDrafter `bbbb00XX`, and RunSupervisor
    `cccc00XX` ranges); deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`), never used to build an LLM.
  - Authorization: the subscriber calls the Authorize port (command
    `PromoteCautionProposal`) before writing the live Caution, parity with
    the human promote path. No separate Policy is seeded (operator-config,
    not seed config).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CautionPromoter agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other seeded
# agents: changing this orphans every prior CautionPromoter-authored
# Decision + Caution (their actor_id pointers go stale). UUID is in the
# deployment-controlled `dddd00XX` range (fourth agent).
CAUTION_PROMOTER_AGENT_ID = UUID("01900000-0000-7000-8000-0000dddd0010")
CAUTION_PROMOTER_AGENT_NAME = "CautionPromoter"
CAUTION_PROMOTER_AGENT_KIND = "CautionPromoter"
CAUTION_PROMOTER_AGENT_VERSION = "1.0.0"
CAUTION_PROMOTER_AGENT_DESCRIPTION = (
    "Deterministic agent: auto-promotes high-confidence, Notice-only "
    "CautionProposal Decisions (drafted by CautionDrafter) into live Cautions, "
    "recording one Decision(context=CautionPromotion) per proposal. Notice-only "
    "and reversible; the operator promotes higher severities."
)


# Sentinel model ref: CautionPromoter is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build an
# LLM (the subscriber's gate is a deterministic check, no build_llm call).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:CautionPromoter:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000dddd0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000dddd0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000dddd0014")


async def seed_caution_promoter_agent(kernel: Kernel) -> None:
    """Seed the CautionPromoter Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAUTION_PROMOTER_AGENT_ID,
        name=CAUTION_PROMOTER_AGENT_NAME,
        kind=CAUTION_PROMOTER_AGENT_KIND,
        version=CAUTION_PROMOTER_AGENT_VERSION,
        description=CAUTION_PROMOTER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCautionPromoterAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAUTION_PROMOTER_AGENT_DESCRIPTION",
    "CAUTION_PROMOTER_AGENT_ID",
    "CAUTION_PROMOTER_AGENT_KIND",
    "CAUTION_PROMOTER_AGENT_NAME",
    "CAUTION_PROMOTER_AGENT_VERSION",
    "seed_caution_promoter_agent",
]
