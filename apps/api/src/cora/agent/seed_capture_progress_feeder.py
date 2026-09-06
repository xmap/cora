"""Bootstrap-time seed for the CaptureProgressFeeder Agent.

The CaptureProgressFeeder runtime (`cora.api._capture_progress_feeder`)
needs an Agent record (and its co-registered Actor) to exist at the
pinned `CAPTURE_PROGRESS_FEEDER_AGENT_ID` so it can issue
`AppendObservations` as an agent-kind principal when it flushes a
witnessed Run's buffered progress readings (`images_saved`,
`images_collected`). Mirrors
`cora.agent.seed_run_witness.seed_run_witness_agent` verbatim except
for the per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

  - Pinned UUID continues the numeric-mnemonic range RunInitiator
    opened at `1111` and RunWitness continued at `2222`; this is the
    next unclaimed block, `3333`. Deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a Rule brain
    (`BrainRef.for_rule("CaptureProgressFeeder:v1")`). Never used to build an LLM: the
    runtime is a buffer-and-flush loop, not an LLM subscriber.
  - A SEPARATE principal from RunTranslator, deliberately: an operator can
    revoke progress-writing (this grant) without blinding the translator
    (RunTranslator's own four grants), and `Observation.actor_id` tells
    the two runtimes' rows apart in the record. The ONLY lever that
    actually revokes it is removing this principal from the Policy's
    `permitted_principal_ids` (a Policy edit): `AppendObservations` is
    liveness-exempt (`cora.shared.liveness`), so deactivating this
    Agent's Actor (`ActorDeactivated`) has NO effect on it, unlike
    RunTranslator, where three of its four grants ARE liveness-gated.
  - Authorization: the runtime issues exactly one command,
    `AppendObservations`, through the Authorize port like any
    principal. Under the default AllowAllAuthorize it is permitted;
    under TrustAuthorize the operator's single configured Policy must
    include this principal + `{AppendObservations}`. Without the
    grant, a real flush logs `capture_progress.append_unauthorized` and
    suppresses that flush's heartbeat too (see
    `CaptureProgressFeeder._flush_observations`): a heartbeat is
    itself a coverage claim, and firing it over a window this
    principal was denied the right to write to would assert coverage
    that never happened.

    `AppendObservations`'s decider carries NO `conduct_mode` gate: it
    accepts any Running-or-Held Run, driven ones included, the same as
    every other operator-facing entry writer. This principal's safety
    therefore rests entirely on `CaptureProgressFeeder` only ever
    sourcing a `run_id` from `RunTranslator.open_captures`, which
    is populated exclusively from RunTranslator's own promotions -- this
    process's, or a prior one's via the boot-time
    `rebuild_open_captures`, itself scoped to `conduct_mode="Witnessed"`
    Runs only -- so it can only ever name a Run RunTranslator created. A
    future change to `_capture_progress_feeder.py` that sources a
    `run_id` for this call from anywhere else would lose that guarantee
    with no decider-level backstop to catch it. Same structural
    residual as the one already documented for RunTranslator's own
    `TruncateRun` grant in `seed_run_translator.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CaptureProgressFeeder agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_WITNESS_AGENT_ID` / `RUN_SUPERVISOR_AGENT_ID`: changing this
# orphans every prior CaptureProgressFeeder-authored Observation's
# `actor_id` pointer. UUID continues the `1111`/`2222`-opened numeric
# range at `3333` (next unclaimed block).
CAPTURE_PROGRESS_FEEDER_AGENT_ID = UUID("01900000-0000-7000-8000-000033330010")
CAPTURE_PROGRESS_FEEDER_AGENT_NAME = "CaptureProgressFeeder"
CAPTURE_PROGRESS_FEEDER_AGENT_KIND = "CaptureProgressFeeder"
CAPTURE_PROGRESS_FEEDER_AGENT_VERSION = "1.0.0"
CAPTURE_PROGRESS_FEEDER_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: buffers a witnessed Run's "
    "capture-progress readings (images saved, images collected) and "
    "flushes them as AppendObservations batches plus a feed heartbeat, "
    "scoped exclusively to Runs RunTranslator itself promoted. Not a "
    "control path: it never drives the substrate, only records what a "
    "promoted capture reported."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000033330012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000033330013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000033330014")


async def seed_capture_progress_feeder_agent(kernel: Kernel) -> None:
    """Seed the CaptureProgressFeeder Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAPTURE_PROGRESS_FEEDER_AGENT_ID,
        name=CAPTURE_PROGRESS_FEEDER_AGENT_NAME,
        kind=CAPTURE_PROGRESS_FEEDER_AGENT_KIND,
        version=CAPTURE_PROGRESS_FEEDER_AGENT_VERSION,
        description=CAPTURE_PROGRESS_FEEDER_AGENT_DESCRIPTION,
        brain=BrainRef.for_rule("CaptureProgressFeeder:v1"),
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCaptureProgressFeederAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAPTURE_PROGRESS_FEEDER_AGENT_DESCRIPTION",
    "CAPTURE_PROGRESS_FEEDER_AGENT_ID",
    "CAPTURE_PROGRESS_FEEDER_AGENT_KIND",
    "CAPTURE_PROGRESS_FEEDER_AGENT_NAME",
    "CAPTURE_PROGRESS_FEEDER_AGENT_VERSION",
    "seed_capture_progress_feeder_agent",
]
