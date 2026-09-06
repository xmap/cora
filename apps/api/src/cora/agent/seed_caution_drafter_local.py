"""Bootstrap-time seed for the local (in-house) CautionDrafter arm.

Mirrors `cora.agent.seed_run_debriefer_local`'s reasoning exactly, for
the `CautionDrafter` kind instead: `kind` stays shared with the
Anthropic-backed default, `model_ref` names the facility-hosted open
model, and the id is its own. A deployment whose `LLM_PROVIDER=local`
designates this Agent (`Settings.caution_drafter_agent_id`) instead of
the vendor-API default.

Named bare `CautionDrafter` by convention: local/in-house arm carries no
suffix, the vendor-API sibling is marked `CautionDrafter (External)`
(see `seed_caution_drafter_external.py`).

`model_ref` points at the generic `"local-model"` catalog entry
(`cora.agent.seed_language_models`), not the older facility-named
`"2bm-inhouse"` entry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef, ModelRef
from cora.agent.prompts import CAUTION_DRAFTER_PROMPT_TEMPLATE_ID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CautionDrafter (local) agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE, same rationale as `CAUTION_DRAFTER_AGENT_ID`. New
# `20ca00XX` range (unused by any other seeded agent as of this writing;
# sibling to RunDebriefer local's `10ca00XX` range).
CAUTION_DRAFTER_LOCAL_AGENT_ID = UUID("01900000-0000-7000-8000-000020ca0010")
CAUTION_DRAFTER_LOCAL_AGENT_NAME = "CautionDrafter"
CAUTION_DRAFTER_LOCAL_AGENT_KIND = "CautionDrafter"
CAUTION_DRAFTER_LOCAL_AGENT_VERSION = "1.0.0"
CAUTION_DRAFTER_LOCAL_AGENT_DESCRIPTION = (
    "Advisory LLM agent: subscribes to terminal Run events and emits one "
    "Decision(context=CautionProposal) per event with a closed 5-choice "
    "verdict (NoAction / ProposeNotice / ProposeCaution / ProposeWarning / "
    "ProposeSupersede) + proposed-Caution payload. Operator promotes via "
    "promote_caution_proposal slice. Never writes Cautions directly. Served "
    "by a facility-hosted open model rather than a vendor API."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000020ca0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000020ca0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000020ca0014")


async def seed_caution_drafter_local_agent(kernel: Kernel) -> None:
    """Seed the local CautionDrafter Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAUTION_DRAFTER_LOCAL_AGENT_ID,
        name=CAUTION_DRAFTER_LOCAL_AGENT_NAME,
        kind=CAUTION_DRAFTER_LOCAL_AGENT_KIND,
        version=CAUTION_DRAFTER_LOCAL_AGENT_VERSION,
        description=CAUTION_DRAFTER_LOCAL_AGENT_DESCRIPTION,
        brain=BrainRef.for_model(ModelRef(provider="local", model="local-model")),
        prompt_template_id=CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCautionDrafterLocalAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAUTION_DRAFTER_LOCAL_AGENT_DESCRIPTION",
    "CAUTION_DRAFTER_LOCAL_AGENT_ID",
    "CAUTION_DRAFTER_LOCAL_AGENT_KIND",
    "CAUTION_DRAFTER_LOCAL_AGENT_NAME",
    "CAUTION_DRAFTER_LOCAL_AGENT_VERSION",
    "seed_caution_drafter_local_agent",
]
