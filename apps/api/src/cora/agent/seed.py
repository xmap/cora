"""Bootstrap-time seed for the RunDebriefer Agent.

No longer the compile-time default: `cora.agent.seed_run_debriefer_external`
now fills that role, and `RUN_DEBRIEFER_EXTERNAL_AGENT_ID` is what
`report_designated_agents` and the subscriber fall back to when no
deployment override is configured. This module and its call in
`cora.api.main` stay exactly as they are anyway, per the id's own
FOREVER-STABLE rule below: a deployment that already carries this
agent retires it with `deprecate_agent`, and a fresh deployment simply
ends up with an extra, Versioned-but-not-default sibling, which is the
same shape `cora.agent.seed_language_models` already ships for its
unused-by-default catalog entries.

`RUN_DEBRIEFER_AGENT_NAME` changed from bare `"RunDebriefer"` to
`"RunDebriefer (Legacy)"` for the same reason: the bare name now belongs
to `cora.agent.seed_run_debriefer_local`'s sibling (the local/in-house
arm carries no suffix; see that module's docstring for the naming
convention), and `SEEDED_FLEET` requires every name to be unique. This
is a source-level change only -- an id whose `AgentDefined` event was
already appended (2-BM's) keeps whatever name that event recorded,
immutably, regardless of what this constant says now. Only a stream
that has never been defined reads the new value.

The RunDebriefer subscriber needs an Agent record (and its
co-registered Actor) to exist at the pinned
`RUN_DEBRIEFER_AGENT_ID` so it can set `Decision.actor_id` without
a lookup. This module defines:

  - The deployment-stable identity constants
    (`RUN_DEBRIEFER_AGENT_ID` + name / kind / version / description).
    Hosted here, NOT in the Agent aggregate's `state.py`, because
    they are deployment seed config, not aggregate-invariant
    declarations. Per cross-BC gate-review convention.
  - The `seed_run_debriefer_agent(kernel)` callable invoked from
    the FastAPI lifespan AFTER `build_kernel` returns the Kernel.

The shared bootstrap scaffolding (envelope build, atomic
`append_streams`, ConcurrencyError-as-no-op, PII vault upsert)
lives in `cora.agent._agent_seed` and is reused verbatim by every
singleton Agent's seed wrapper.

## Why a fixed UUID

Most CORA aggregates get server-allocated UUIDv7 ids. The
RunDebriefer agent is a singleton-per-deployment whose id is
referenced by the subscriber + the deterministic decision-id
derivation. Pinning the id to a constant (per
[[project_run_debrief_design]]) lets the bootstrap re-run safely on
every restart without needing a "find or create" lookup.

## Principal_id

The bootstrap envelope uses `SYSTEM_PRINCIPAL_ID`, NOT the
agent's own id. The agent doesn't exist yet at boot-time, so
self-attribution would be a circular-causation lie in the event
envelope. `SYSTEM_PRINCIPAL_ID` is the conventional value for
"the system did this before any human auth context existed"
writes; the seed is one such write.

## Wiring

Called from the FastAPI lifespan after `build_kernel` and after
the Postgres pool is alive. If `kernel.event_store` is in-memory
(test mode), the seed still runs and writes to memory; tests can
opt out by not calling the seed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef, ModelRef
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunDebriefer agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Changing this id would orphan every prior
# RunDebriefer-authored Decision (their actor_id pointers go stale),
# break the subscriber's deterministic decision_id derivation for
# events already processed, and require a manual migration to
# re-assign actor_id on every historical RunDebriefer Decision.
# The id is in the deployment-controlled `aaaa00XX` UUID range
# alongside other RunDebriefer-related constants (prompt template id,
# decision-id namespace, bootstrap event ids); see the registry
# table in the file-level comment of `cora.agent.prompts.run_debrief`
# for the allocation scheme.
RUN_DEBRIEFER_AGENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0010")
RUN_DEBRIEFER_AGENT_NAME = "RunDebriefer (Legacy)"
RUN_DEBRIEFER_AGENT_KIND = "RunDebriefer"
RUN_DEBRIEFER_AGENT_VERSION = "1.0.0"
RUN_DEBRIEFER_AGENT_DESCRIPTION = (
    "Advisory LLM agent: writes one Decision per terminal Run event with a "
    "closed-set choice + 130-230 word BLUF + 4-section AAR narrative. "
    "Observer-only; never gates Run state."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

# Each event's event_id is deterministic so a retried seed attempt
# produces the same envelope id (event_store UNIQUE constraint on
# event_id makes the second attempt a no-op even if ConcurrencyError
# didn't catch first).
_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000aaaa0014")


async def seed_run_debriefer_agent(kernel: Kernel) -> None:
    """Seed the RunDebriefer Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_DEBRIEFER_AGENT_ID,
        name=RUN_DEBRIEFER_AGENT_NAME,
        kind=RUN_DEBRIEFER_AGENT_KIND,
        version=RUN_DEBRIEFER_AGENT_VERSION,
        description=RUN_DEBRIEFER_AGENT_DESCRIPTION,
        brain=BrainRef.for_model(
            ModelRef(
                provider=DEFAULT_RUN_DEBRIEF_MODEL.provider,
                model=DEFAULT_RUN_DEBRIEF_MODEL.model,
                snapshot_pin=DEFAULT_RUN_DEBRIEF_MODEL.snapshot_pin,
            )
        ),
        prompt_template_id=RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunDebrieferAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_DEBRIEFER_AGENT_DESCRIPTION",
    "RUN_DEBRIEFER_AGENT_ID",
    "RUN_DEBRIEFER_AGENT_KIND",
    "RUN_DEBRIEFER_AGENT_NAME",
    "RUN_DEBRIEFER_AGENT_VERSION",
    "seed_run_debriefer_agent",
]
