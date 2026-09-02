"""Bootstrap-time seed for the vendor-API RunDebriefer arm.

Replaces `cora.agent.seed.seed_run_debriefer_agent`'s role as the
compile-time default the RunDebriefer subscriber falls back to when no
deployment override is configured (`Settings.run_debriefer_agent_id`).
The old agent (`RUN_DEBRIEFER_AGENT_ID`, `aaaa0010`) is not deleted or
reassigned; per [[project_agent_bc_design]] `AgentName` is immutable and
ids are FOREVER-STABLE, so a new identity was minted instead and the old
one is retired via `deprecate_agent` on deployments that carry it (see
`cora.agent.seed`'s module docstring for the supersession note).

Named `RunDebriefer (External)` by convention: the vendor-API arm is
marked, the local/in-house arm is bare (see `seed_run_debriefer_local.py`).
"External" pairs with this codebase's own "In-House" vocabulary
(`ServingRoute.IN_HOUSE`, the `cora.agent.seed_language_models` catalog)
rather than introducing a second word for the same in-house/not-in-house
axis.

`model_ref` is unchanged from the original default
(`DEFAULT_RUN_DEBRIEF_MODEL`): this agent is a rename+re-id of the same
Anthropic-backed identity, not a different model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunDebriefer (External) agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE, same rationale as `RUN_DEBRIEFER_AGENT_ID`. New
# `9aaa00XX` range (unused by any other seeded agent as of this writing;
# chosen near the retired `aaaa00XX` range to signal lineage, not to be
# confused with it).
RUN_DEBRIEFER_EXTERNAL_AGENT_ID = UUID("01900000-0000-7000-8000-00009aaa0010")
RUN_DEBRIEFER_EXTERNAL_AGENT_NAME = "RunDebriefer (External)"
RUN_DEBRIEFER_EXTERNAL_AGENT_KIND = "RunDebriefer"
RUN_DEBRIEFER_EXTERNAL_AGENT_VERSION = "1.0.0"
RUN_DEBRIEFER_EXTERNAL_AGENT_DESCRIPTION = (
    "Advisory LLM agent: writes one Decision per terminal Run event with a "
    "closed-set choice + 130-230 word BLUF + 4-section AAR narrative. "
    "Observer-only; never gates Run state. The compile-time default "
    "RunDebriefer, served by a vendor API."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-00009aaa0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-00009aaa0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-00009aaa0014")


async def seed_run_debriefer_external_agent(kernel: Kernel) -> None:
    """Seed the external RunDebriefer Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_DEBRIEFER_EXTERNAL_AGENT_ID,
        name=RUN_DEBRIEFER_EXTERNAL_AGENT_NAME,
        kind=RUN_DEBRIEFER_EXTERNAL_AGENT_KIND,
        version=RUN_DEBRIEFER_EXTERNAL_AGENT_VERSION,
        description=RUN_DEBRIEFER_EXTERNAL_AGENT_DESCRIPTION,
        model_ref=ModelRef(
            provider=DEFAULT_RUN_DEBRIEF_MODEL.provider,
            model=DEFAULT_RUN_DEBRIEF_MODEL.model,
            snapshot_pin=DEFAULT_RUN_DEBRIEF_MODEL.snapshot_pin,
        ),
        prompt_template_id=RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunDebrieferExternalAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_DEBRIEFER_EXTERNAL_AGENT_DESCRIPTION",
    "RUN_DEBRIEFER_EXTERNAL_AGENT_ID",
    "RUN_DEBRIEFER_EXTERNAL_AGENT_KIND",
    "RUN_DEBRIEFER_EXTERNAL_AGENT_NAME",
    "RUN_DEBRIEFER_EXTERNAL_AGENT_VERSION",
    "seed_run_debriefer_external_agent",
]
