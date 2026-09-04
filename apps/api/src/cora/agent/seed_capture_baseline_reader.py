"""Bootstrap-time seed for the CaptureBaselineReader Agent.

The CaptureBaselineReader runtime (`cora.api._capture_baseline_reader`)
needs an Agent record (and its co-registered Actor) to exist at the
pinned `CAPTURE_BASELINE_READER_AGENT_ID` so it can issue
`AppendObservations` as an agent-kind principal when it reads a
witnessed Run's genesis-baseline PVs (slice 12) at promotion. Mirrors
`cora.agent.seed_capture_progress_feeder.seed_capture_progress_feeder_agent`
verbatim except for the per-agent constants below; the shared
scaffolding lives in `cora.agent._agent_seed`.

  - Pinned UUID opens a new mnemonic block, `ba5e` ("BASE"), distinct
    from RunInitiator's `1111`, RunWitness's `2222`, and
    CaptureProgressFeeder's `3333`. Deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a Rule brain
    (`BrainRef.for_rule("CaptureBaselineReader:v1")`). Never used to build an LLM: the
    runtime is a one-shot read-and-append at promotion, not an LLM
    subscriber.
  - A SEPARATE principal from RunTranslator AND from CaptureProgressFeeder,
    deliberately, for the same reason CaptureProgressFeeder already got
    its own: an operator can revoke baseline-writing (this grant)
    without blinding either the translator or the progress feeder, and
    `Observation.actor_id` tells all three runtimes' rows apart in the
    record even though `sampling_procedure` already discriminates
    baseline from monitor rows. The ONLY lever that actually revokes it
    is removing this principal from the Policy's
    `permitted_principal_ids` (a Policy edit): `AppendObservations` is
    liveness-exempt (`cora.shared.liveness`), so deactivating this
    Agent's Actor (`ActorDeactivated`) has NO effect on it, exactly as
    documented for CaptureProgressFeeder.
  - Authorization: the runtime issues exactly one command,
    `AppendObservations`, through the Authorize port like any
    principal. Under the default AllowAllAuthorize it is permitted;
    under TrustAuthorize the operator's single configured Policy must
    include this principal + `{AppendObservations}`. Without the
    grant, a real baseline read logs `capture_baseline.append_unauthorized`
    and the reading is simply lost for that Run: unlike
    CaptureProgressFeeder there is no heartbeat to suppress, since a
    one-time genesis snapshot carries no ongoing liveness claim.

    `AppendObservations`'s decider carries NO `conduct_mode` gate: it
    accepts any Running-or-Held Run, driven ones included, the same as
    every other operator-facing entry writer. This principal's safety
    rests entirely on `CaptureBaselineReader.read` only ever
    being called by `RunTranslator._promote` with the `run_id` it
    JUST minted via `record_witnessed_run`, never a run_id sourced any
    other way. Same structural residual already documented for
    RunTranslator's own `TruncateRun` grant in `seed_run_translator.py` and
    for CaptureProgressFeeder's `AppendObservations` grant above it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CaptureBaselineReader agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `CAPTURE_PROGRESS_FEEDER_AGENT_ID` / `RUN_WITNESS_AGENT_ID`: changing
# this orphans every prior CaptureBaselineReader-authored Observation's
# `actor_id` pointer. UUID opens the `ba5e` ("BASE") mnemonic block.
CAPTURE_BASELINE_READER_AGENT_ID = UUID("01900000-0000-7000-8000-0000ba5e0010")
CAPTURE_BASELINE_READER_AGENT_NAME = "CaptureBaselineReader"
CAPTURE_BASELINE_READER_AGENT_KIND = "CaptureBaselineReader"
CAPTURE_BASELINE_READER_AGENT_VERSION = "1.0.0"
CAPTURE_BASELINE_READER_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: reads a deployment-declared set of "
    "genesis-baseline PVs exactly once, at the instant a capture promotes "
    "to a witnessed Run, and appends them as AppendObservations rows with "
    'sampling_procedure="baseline", scoped exclusively to the Run '
    "RunTranslator itself just promoted. Not a control path: it never drives "
    "the substrate, only records what it read at that moment."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000ba5e0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000ba5e0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000ba5e0014")


async def seed_capture_baseline_reader_agent(kernel: Kernel) -> None:
    """Seed the CaptureBaselineReader Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAPTURE_BASELINE_READER_AGENT_ID,
        name=CAPTURE_BASELINE_READER_AGENT_NAME,
        kind=CAPTURE_BASELINE_READER_AGENT_KIND,
        version=CAPTURE_BASELINE_READER_AGENT_VERSION,
        description=CAPTURE_BASELINE_READER_AGENT_DESCRIPTION,
        brain=BrainRef.for_rule("CaptureBaselineReader:v1"),
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCaptureBaselineReaderAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAPTURE_BASELINE_READER_AGENT_DESCRIPTION",
    "CAPTURE_BASELINE_READER_AGENT_ID",
    "CAPTURE_BASELINE_READER_AGENT_KIND",
    "CAPTURE_BASELINE_READER_AGENT_NAME",
    "CAPTURE_BASELINE_READER_AGENT_VERSION",
    "seed_capture_baseline_reader_agent",
]
