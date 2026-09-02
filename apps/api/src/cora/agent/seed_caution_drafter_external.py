"""Bootstrap-time seed for the vendor-API CautionDrafter arm.

Mirrors `cora.agent.seed_run_debriefer_external`'s reasoning exactly,
for the `CautionDrafter` kind instead: replaces
`cora.agent.seed_caution_drafter.seed_caution_drafter_agent`'s role as
the compile-time default the CautionDrafter subscriber falls back to
when no deployment override is configured
(`Settings.caution_drafter_agent_id`). The old agent
(`CAUTION_DRAFTER_AGENT_ID`, `bbbb0010`) is not deleted or reassigned;
a new identity was minted instead and the old one is retired via
`deprecate_agent` on deployments that carry it.

Named `CautionDrafter (External)` by convention: vendor-API arm is
marked, local/in-house arm is bare (see `seed_caution_drafter_local.py`).

`model_ref` is unchanged from the original default
(`DEFAULT_CAUTION_DRAFTER_MODEL`): this agent is a rename+re-id of the
same Anthropic-backed identity, not a different model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef
from cora.agent.prompts import CAUTION_DRAFTER_PROMPT_TEMPLATE_ID
from cora.agent.prompts.caution_drafter import DEFAULT_CAUTION_DRAFTER_MODEL

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CautionDrafter (External) agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE, same rationale as `CAUTION_DRAFTER_AGENT_ID`. New
# `9bbb00XX` range (unused by any other seeded agent as of this writing;
# chosen near the retired `bbbb00XX` range to signal lineage, not to be
# confused with it).
CAUTION_DRAFTER_EXTERNAL_AGENT_ID = UUID("01900000-0000-7000-8000-00009bbb0010")
CAUTION_DRAFTER_EXTERNAL_AGENT_NAME = "CautionDrafter (External)"
CAUTION_DRAFTER_EXTERNAL_AGENT_KIND = "CautionDrafter"
CAUTION_DRAFTER_EXTERNAL_AGENT_VERSION = "1.0.0"
CAUTION_DRAFTER_EXTERNAL_AGENT_DESCRIPTION = (
    "Advisory LLM agent: subscribes to terminal Run events and emits one "
    "Decision(context=CautionProposal) per event with a closed 5-choice "
    "verdict (NoAction / ProposeNotice / ProposeCaution / ProposeWarning / "
    "ProposeSupersede) + proposed-Caution payload. Operator promotes via "
    "promote_caution_proposal slice. Never writes Cautions directly. The "
    "compile-time default CautionDrafter, served by a vendor API."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-00009bbb0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-00009bbb0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-00009bbb0014")


async def seed_caution_drafter_external_agent(kernel: Kernel) -> None:
    """Seed the external CautionDrafter Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAUTION_DRAFTER_EXTERNAL_AGENT_ID,
        name=CAUTION_DRAFTER_EXTERNAL_AGENT_NAME,
        kind=CAUTION_DRAFTER_EXTERNAL_AGENT_KIND,
        version=CAUTION_DRAFTER_EXTERNAL_AGENT_VERSION,
        description=CAUTION_DRAFTER_EXTERNAL_AGENT_DESCRIPTION,
        model_ref=ModelRef(
            provider=DEFAULT_CAUTION_DRAFTER_MODEL.provider,
            model=DEFAULT_CAUTION_DRAFTER_MODEL.model,
            snapshot_pin=DEFAULT_CAUTION_DRAFTER_MODEL.snapshot_pin,
        ),
        prompt_template_id=CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCautionDrafterExternalAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAUTION_DRAFTER_EXTERNAL_AGENT_DESCRIPTION",
    "CAUTION_DRAFTER_EXTERNAL_AGENT_ID",
    "CAUTION_DRAFTER_EXTERNAL_AGENT_KIND",
    "CAUTION_DRAFTER_EXTERNAL_AGENT_NAME",
    "CAUTION_DRAFTER_EXTERNAL_AGENT_VERSION",
    "seed_caution_drafter_external_agent",
]
