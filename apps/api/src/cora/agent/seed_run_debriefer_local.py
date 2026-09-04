"""Bootstrap-time seed for the local (in-house) RunDebriefer arm.

Same job as `cora.agent.seed.seed_run_debriefer_agent`, different brain:
`kind="RunDebriefer"` is shared, `model_ref` names the facility-hosted
open model instead of Anthropic's, and the id is its own so the two can
be `Versioned` concurrently (per `aggregates/agent/state.py`:
"Multiple Versioned Agents may exist concurrently... different `id`s
sharing `kind`"). A deployment whose `LLM_PROVIDER=local` designates
this Agent (`Settings.run_debriefer_agent_id`) instead of the Anthropic
default, since the LLM adapter refuses any call whose `model_ref.provider`
doesn't match the deployment's configured provider.

Named bare `RunDebriefer` (no parenthetical), by convention: the
local/in-house arm carries no suffix, the vendor-API sibling is marked
`RunDebriefer (External)` (see `seed_run_debriefer_external.py`). Chosen
over embedding a model name in the display name because the model can
change (a facility can retarget its GPU box to a different open model
without a new Agent identity, per `cora.agent.seed_language_models`'s
in-house catalog entry), while "local" as a serving-route distinction
does not.

`model_ref` points at the generic `"local-model"` catalog entry
(`cora.agent.seed_language_models`), not the older facility-named
`"2bm-inhouse"` entry: a governance identifier that could be reused by
any facility's own local deployment, not just 2-BM's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef, ModelRef
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunDebriefer (local) agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE, same rationale as `RUN_DEBRIEFER_AGENT_ID`. New
# `10ca00XX` range (unused by any other seeded agent as of this writing).
RUN_DEBRIEFER_LOCAL_AGENT_ID = UUID("01900000-0000-7000-8000-000010ca0010")
RUN_DEBRIEFER_LOCAL_AGENT_NAME = "RunDebriefer"
RUN_DEBRIEFER_LOCAL_AGENT_KIND = "RunDebriefer"
RUN_DEBRIEFER_LOCAL_AGENT_VERSION = "1.0.0"
RUN_DEBRIEFER_LOCAL_AGENT_DESCRIPTION = (
    "Advisory LLM agent: writes one Decision per terminal Run event with a "
    "closed-set choice + 130-230 word BLUF + 4-section AAR narrative. "
    "Observer-only; never gates Run state. Served by a facility-hosted "
    "open model rather than a vendor API."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000010ca0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000010ca0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000010ca0014")


async def seed_run_debriefer_local_agent(kernel: Kernel) -> None:
    """Seed the local RunDebriefer Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_DEBRIEFER_LOCAL_AGENT_ID,
        name=RUN_DEBRIEFER_LOCAL_AGENT_NAME,
        kind=RUN_DEBRIEFER_LOCAL_AGENT_KIND,
        version=RUN_DEBRIEFER_LOCAL_AGENT_VERSION,
        description=RUN_DEBRIEFER_LOCAL_AGENT_DESCRIPTION,
        brain=BrainRef.for_model(ModelRef(provider="local", model="local-model")),
        prompt_template_id=RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunDebrieferLocalAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_DEBRIEFER_LOCAL_AGENT_DESCRIPTION",
    "RUN_DEBRIEFER_LOCAL_AGENT_ID",
    "RUN_DEBRIEFER_LOCAL_AGENT_KIND",
    "RUN_DEBRIEFER_LOCAL_AGENT_NAME",
    "RUN_DEBRIEFER_LOCAL_AGENT_VERSION",
    "seed_run_debriefer_local_agent",
]
