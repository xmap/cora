"""Bootstrap-time seed for the RunWatcher Agent.

The RunWatcher runtime (`cora.api._run_watcher`) needs an Agent record
(and its co-registered Actor) to exist at the pinned `RUN_WATCHER_AGENT_ID`
so it can issue `RecordWatchedRun` as an agent-kind principal when it
promotes a BEGUN capture observation to a real watched Run. Mirrors
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
  - Authorization: the runtime issues `RecordWatchedRun` through the
    Authorize port like any principal. Under the default AllowAllAuthorize
    it is permitted; under TrustAuthorize the operator's single configured
    Policy must include this principal + {RecordWatchedRun, ListRuns}.
    ListRuns is the restart-rebuild read: without it a restart cannot
    rediscover which captures are already open, and would re-promote
    them. Without the RecordWatchedRun grant, a real BEGUN observation
    logs `run_watcher.promotion_unauthorized` and stays IDLE (retried on
    the next BEGUN, same posture as RunInitiator's StartRun grant).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunWatcher agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_SUPERVISOR_AGENT_ID` / `RUN_INITIATOR_AGENT_ID`: changing this
# orphans every prior RunWatcher-authored Run's principal_id pointer.
# UUID continues the `1111`-opened numeric range at `2222` (next unclaimed
# block).
RUN_WATCHER_AGENT_ID = UUID("01900000-0000-7000-8000-000022220010")
RUN_WATCHER_AGENT_NAME = "RunWatcher"
RUN_WATCHER_AGENT_KIND = "RunWatcher"
RUN_WATCHER_AGENT_VERSION = "1.0.0"
RUN_WATCHER_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: promotes a real watched (Recorded) "
    "Run via record_watched_run when it observes an external tool "
    "(TomoScan) begin a capture, with per-capture-code dedup so a single "
    "in-progress capture is never promoted twice. Not a control path: it "
    "never drives the substrate, only records that a capture already "
    "began."
)


# Sentinel model ref: RunWatcher is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build
# an LLM (no subscriber / no build_llm call for this agent).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:RunWatcher:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000022220012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000022220013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000022220014")


async def seed_run_watcher_agent(kernel: Kernel) -> None:
    """Seed the RunWatcher Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_WATCHER_AGENT_ID,
        name=RUN_WATCHER_AGENT_NAME,
        kind=RUN_WATCHER_AGENT_KIND,
        version=RUN_WATCHER_AGENT_VERSION,
        description=RUN_WATCHER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunWatcherAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_WATCHER_AGENT_DESCRIPTION",
    "RUN_WATCHER_AGENT_ID",
    "RUN_WATCHER_AGENT_KIND",
    "RUN_WATCHER_AGENT_NAME",
    "RUN_WATCHER_AGENT_VERSION",
    "seed_run_watcher_agent",
]
