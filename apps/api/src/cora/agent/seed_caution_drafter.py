"""Bootstrap-time seed for the CautionDrafter Agent.

No longer the compile-time default: `cora.agent.seed_caution_drafter_external`
now fills that role. See `cora.agent.seed`'s module docstring for the full
supersession note (same reasoning applies here verbatim).

The CautionDrafter subscriber needs an Agent record (and its
co-registered Actor) to exist at the pinned
`CAUTION_DRAFTER_AGENT_ID` so it can set `Decision.actor_id`
without a lookup. Mirrors `cora.agent.seed.seed_run_debriefer_agent`
verbatim except for the per-agent constants below; the shared
scaffolding lives in `cora.agent._agent_seed`.

Per [[project_caution_drafter_design]] Locks:
  - Pinned UUID in the `bbbb00XX` range (sibling to the
    `aaaa00XX` RunDebriefer range); deployment-stable forever.
  - Atomic cross-BC write of `ActorRegistered(kind="agent")` +
    `AgentDefined` via `EventStore.append_streams`.
  - Envelope's `principal_id = SYSTEM_PRINCIPAL_ID` (NOT
    self-reference; agent doesn't exist yet at boot).
  - `ConcurrencyError`-as-no-op for restart idempotency.
  - Default model = `claude-sonnet-4-6` (CautionDrafter's task is
    more nuanced than RunDebriefer's classification; warrants
    Sonnet over Haiku).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef, ModelRef
from cora.agent.prompts.caution_drafter import (
    CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
    DEFAULT_CAUTION_DRAFTER_MODEL,
)

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CautionDrafter agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_DEBRIEFER_AGENT_ID`: changing this orphans every prior
# CautionDrafter-authored Decision and breaks the subscriber's
# deterministic decision_id derivation.
#
# UUID is in the deployment-controlled `bbbb00XX` range (sibling
# to RunDebriefer's `aaaa00XX` range). Future agents (#3+) get
# their own `cccc00XX` / `dddd00XX` / etc ranges so the bootstrap
# constants stay visually grouped per agent.
CAUTION_DRAFTER_AGENT_ID = UUID("01900000-0000-7000-8000-0000bbbb0010")
CAUTION_DRAFTER_AGENT_NAME = "CautionDrafter (Legacy)"
CAUTION_DRAFTER_AGENT_KIND = "CautionDrafter"
CAUTION_DRAFTER_AGENT_VERSION = "1.0.0"
CAUTION_DRAFTER_AGENT_DESCRIPTION = (
    "Advisory LLM agent: subscribes to terminal Run events and emits one "
    "Decision(context=CautionProposal) per event with a closed 5-choice "
    "verdict (NoAction / ProposeNotice / ProposeCaution / ProposeWarning / "
    "ProposeSupersede) + proposed-Caution payload. Operator promotes via "
    "promote_caution_proposal slice. Never writes Cautions directly."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000bbbb0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000bbbb0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000bbbb0014")


async def seed_caution_drafter_agent(kernel: Kernel) -> None:
    """Seed the CautionDrafter Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAUTION_DRAFTER_AGENT_ID,
        name=CAUTION_DRAFTER_AGENT_NAME,
        kind=CAUTION_DRAFTER_AGENT_KIND,
        version=CAUTION_DRAFTER_AGENT_VERSION,
        description=CAUTION_DRAFTER_AGENT_DESCRIPTION,
        brain=BrainRef.for_model(
            ModelRef(
                provider=DEFAULT_CAUTION_DRAFTER_MODEL.provider,
                model=DEFAULT_CAUTION_DRAFTER_MODEL.model,
                snapshot_pin=DEFAULT_CAUTION_DRAFTER_MODEL.snapshot_pin,
            )
        ),
        prompt_template_id=CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCautionDrafterAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAUTION_DRAFTER_AGENT_DESCRIPTION",
    "CAUTION_DRAFTER_AGENT_ID",
    "CAUTION_DRAFTER_AGENT_KIND",
    "CAUTION_DRAFTER_AGENT_NAME",
    "CAUTION_DRAFTER_AGENT_VERSION",
    "seed_caution_drafter_agent",
]
