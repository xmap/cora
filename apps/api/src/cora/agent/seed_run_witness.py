"""Bootstrap-time seed for the RunWitness Agent (retired).

Superseded by `seed_run_translator.py`'s `RunTranslator`: same runtime,
same job, renamed because `witness` named the modeling axis this runtime
implements, not what the runtime itself does. This module stays
source-tracked and its boot-time seed call stays in `main.py` forever,
per this identity's own FOREVER-STABLE rule below -- 2-BM's already-
recorded Runs keep `RUN_WITNESS_AGENT_ID` as their `principal_id`
pointer permanently, and a deployment retires this Agent via
`deprecate_agent` rather than losing it from source.

The RunWitness runtime (`cora.api._run_witness`) needs an Agent record
(and its co-registered Actor) to exist at the pinned `RUN_WITNESS_AGENT_ID`
so it can issue `RecordWitnessedRun` as an agent-kind principal when it
promotes a BEGUN capture observation to a real witnessed Run. Mirrors
`cora.agent.seed_run_supervisor.seed_run_supervisor_agent` verbatim except
for the per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

  - Pinned UUID continues the numeric-mnemonic range RunInitiator opened
    at `1111` (the lettered `aaaa`/`bbbb`/`cccc`/`dddd`/`eeee`/`ffff`
    blocks are all claimed); deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`). Never used to build an LLM: the
    runtime is a substrate-observation loop, not an LLM subscriber.
  - Authorization: the runtime issues four distinct commands through the
    Authorize port like any principal. Under the default AllowAllAuthorize
    all four are permitted; under TrustAuthorize the operator's single
    configured Policy must include this principal + {RecordWitnessedRun,
    RecordWitnessedRunOutcome, TruncateRun, ListRuns}. ListRuns is the
    restart-rebuild read: without it a restart cannot rediscover which
    captures are already open, and would re-promote them. Without the
    RecordWitnessedRun grant, a real BEGUN observation logs
    `run_witness.promotion_unauthorized` and stays IDLE (retried on the
    next BEGUN). Without RecordWitnessedRunOutcome, a real terminal logs
    `run_witness.outcome_unauthorized` and leaves the Run open (retried
    on the next BEGUN via truncation). Without TruncateRun, a missed
    terminal cannot be recovered and logs `run_witness.truncate_unauthorized`,
    but the new capture still promotes regardless.

    UNLIKE the RecordWitnessedRunOutcome grant, TruncateRun's decider
    carries no `conduct_mode` gate (it accepts any Running-or-Held Run,
    same as every other operator-facing terminal). This principal's
    safety therefore rests on `_run_witness.py`'s own bookkeeping
    discipline: `_truncate_stale` only ever supplies a `run_id` it
    popped from its own `_open_captures` dict, which is populated
    exclusively by this same runtime's own promotions, so it can only
    ever name a Run it created. A future change to `_run_witness.py`
    that sources a `run_id` for this call from anywhere else would lose
    that guarantee with no decider-level backstop to catch it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunWitness agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_SUPERVISOR_AGENT_ID` / `RUN_INITIATOR_AGENT_ID`: changing this
# orphans every prior RunWitness-authored Run's principal_id pointer.
# UUID continues the `1111`-opened numeric range at `2222` (next unclaimed
# block).
RUN_WITNESS_AGENT_ID = UUID("01900000-0000-7000-8000-000022220010")
RUN_WITNESS_AGENT_NAME = "RunWitness"
RUN_WITNESS_AGENT_KIND = "RunWitness"
RUN_WITNESS_AGENT_VERSION = "1.0.0"
RUN_WITNESS_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: promotes a real Witnessed "
    "Run via record_witnessed_run when it observes an external tool "
    "(TomoScan) begin a capture, with per-capture-code dedup so a single "
    "in-progress capture is never promoted twice. Not a control path: it "
    "never drives the substrate, only records that a capture already "
    "began."
)


# Sentinel model ref: RunWitness is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build
# an LLM (no subscriber / no build_llm call for this agent).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:RunWitness:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000022220012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000022220013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000022220014")


async def seed_run_witness_agent(kernel: Kernel) -> None:
    """Seed the RunWitness Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_WITNESS_AGENT_ID,
        name=RUN_WITNESS_AGENT_NAME,
        kind=RUN_WITNESS_AGENT_KIND,
        version=RUN_WITNESS_AGENT_VERSION,
        description=RUN_WITNESS_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunWitnessAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_WITNESS_AGENT_DESCRIPTION",
    "RUN_WITNESS_AGENT_ID",
    "RUN_WITNESS_AGENT_KIND",
    "RUN_WITNESS_AGENT_NAME",
    "RUN_WITNESS_AGENT_VERSION",
    "seed_run_witness_agent",
]
