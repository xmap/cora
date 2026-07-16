"""Bootstrap-time seed for the RatificationEnforcer Agent (consequence gate, Gate IV).

The RatificationEnforcer is a DETERMINISTIC (non-LLM) subscriber pair that
discharges the consequence gate into the shared hold:
  - on `RatificationRequested`, it HOLDS the target run (appends RunHeld via
    Pattern C, guarding Running in-process, NOT calling the hold_run slice, which
    is off-limits across the tach BC boundary);
  - on `RatificationGranted`, it RESUMES the held run (appends RunResumed).

It needs an Agent record (and its co-registered Actor) at the pinned
`RATIFICATION_ENFORCER_AGENT_ID` so it can hold/resume Runs as an agent-kind
principal and be authz-gated + operator-deactivated like any other agent.

Unlike the kill-switch holder, the enforcer records NO Decision: the Ratification
events themselves (Requested / Granted / Denied) are the provenance.

Mirrors `cora.agent.seed_authority_revocation_holder` except for the per-agent
constants below; the shared scaffolding lives in `cora.agent._agent_seed`.

Per the consequence-gate design (Gate IV, the T-ASE resource-accountability
paper's four-gates plan):
  - Pinned UUID in the deployment-controlled `fac0` range (a hex-valid nod to the
    rati-FIC-ation mnemonic), distinct from every other agent block; deployment-
    stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`), never used to build an LLM. Same Agent-shape
    watch the other rule-agents carry.
  - Authorization: the hold subscriber authorizes HoldRun and the release
    subscriber authorizes ResumeRun through the Authorize port as this principal
    before writing. Under default AllowAllAuthorize both are permitted (bootstrap
    window); under TrustAuthorize the operator's Policy must include this
    principal + {HoldRun, ResumeRun}. Without a grant the action is a logged
    no-op, so the gate degrades safe rather than crashing.
  - Not a safety interlock: the hold is a REVERSIBLE park pending a co-signature
    (resume_run exists), edge-triggered and fail-safe, NOT the floor PSS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RatificationEnforcer agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. UUID is in the deployment-controlled `fac0` range (a
# hex-valid nod to the rati-FIC-ation mnemonic), distinct from every other agent
# block, keeping the bootstrap constants visually grouped per agent.
RATIFICATION_ENFORCER_AGENT_ID = UUID("01900000-0000-7000-8000-0000fac00010")
RATIFICATION_ENFORCER_AGENT_NAME = "RatificationEnforcer"
RATIFICATION_ENFORCER_AGENT_KIND = "RatificationEnforcer"
RATIFICATION_ENFORCER_AGENT_VERSION = "1.0.0"
RATIFICATION_ENFORCER_AGENT_DESCRIPTION = (
    "Deterministic consequence-gate subscriber pair: on a RatificationRequested "
    "holds the target run (parks it pending co-signature); on a "
    "RatificationGranted resumes it. A reversible, fail-safe park of a run "
    "pending a second independent principal's co-sign, not a safety interlock "
    "(the floor PSS owns hard safety)."
)


# Sentinel model ref: the enforcer is rule-based, not an LLM agent. The Agent
# aggregate requires a ModelRef; this value is never used to build an LLM.
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:RatificationEnforcer:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000fac00012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000fac00013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000fac00014")


async def seed_ratification_enforcer_agent(kernel: Kernel) -> None:
    """Seed the RatificationEnforcer Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RATIFICATION_ENFORCER_AGENT_ID,
        name=RATIFICATION_ENFORCER_AGENT_NAME,
        kind=RATIFICATION_ENFORCER_AGENT_KIND,
        version=RATIFICATION_ENFORCER_AGENT_VERSION,
        description=RATIFICATION_ENFORCER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRatificationEnforcerAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RATIFICATION_ENFORCER_AGENT_DESCRIPTION",
    "RATIFICATION_ENFORCER_AGENT_ID",
    "RATIFICATION_ENFORCER_AGENT_KIND",
    "RATIFICATION_ENFORCER_AGENT_NAME",
    "RATIFICATION_ENFORCER_AGENT_VERSION",
    "seed_ratification_enforcer_agent",
]
