"""Bootstrap-time seed for the CaptureScanIngestor Agent.

The CaptureScanIngestor runtime (`cora.api._capture_scan_ingestor`) needs an
Agent record (and its co-registered Actor) to exist at the pinned
`CAPTURE_SCAN_INGESTOR_AGENT_ID` so it can issue `IngestScan` as an
agent-kind principal when its sweep finds a terminated witnessed Run whose
capture path resolved but which has no Dataset yet. Mirrors
`cora.agent.seed_capture_progress_feeder.seed_capture_progress_feeder_agent`
verbatim except for the per-agent constants below; the shared scaffolding
lives in `cora.agent._agent_seed`.

  - Pinned UUID opens a NEW numeric-mnemonic block, `1465` (`INGEST` on a
    phone keypad; the mnemonic ranges already claimed are `1111`
    RunInitiator, `2222` RunWitness, `3333` CaptureProgressFeeder,
    `ba5e` CaptureBaselineReader, `5733` ExperimentSteerer, and the
    hex-word blocks `cab1`/`b111`/`ca11`/`dddd`/`eeee`/`bbbb`/`cccc`/
    `ffff`/`0c0c`/`fac0`). Deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`). The sweep is a poll-and-append loop,
    not an LLM subscriber.
  - A SEPARATE principal from RunTranslator, CaptureProgressFeeder, and
    CaptureBaselineReader, deliberately: an operator can revoke
    scan-ingest (this grant) without blinding any of the other three,
    and `Dataset.registered_by` / `Acquisition.recorded_by` tell this
    runtime's writes apart from a human operator's own `ingest_scan`
    calls in the record.
  - Authorization: the sweep issues exactly one command, `IngestScan`,
    through the Authorize port like any principal. Under
    TrustAuthorize the operator's configured Policy must include this
    principal + `{IngestScan}`. Without the grant, a real sweep tick
    logs `capture_scan_ingestor.ingest_unauthorized` and leaves the
    candidate run for the next tick (see
    `_capture_scan_ingestor.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CaptureScanIngestor agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `CAPTURE_PROGRESS_FEEDER_AGENT_ID` / `CAPTURE_BASELINE_READER_AGENT_ID`:
# changing this orphans every prior CaptureScanIngestor-authored Dataset's
# `registered_by` pointer. UUID opens a new numeric-mnemonic block, `1465`
# (INGEST).
CAPTURE_SCAN_INGESTOR_AGENT_ID = UUID("01900000-0000-7000-8000-000014650010")
CAPTURE_SCAN_INGESTOR_AGENT_NAME = "CaptureScanIngestor"
CAPTURE_SCAN_INGESTOR_AGENT_KIND = "CaptureScanIngestor"
CAPTURE_SCAN_INGESTOR_AGENT_VERSION = "1.0.0"
CAPTURE_SCAN_INGESTOR_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: sweeps terminated witnessed Runs "
    "whose observed capture path resolved and which have no Dataset yet, "
    "and ingests each as a Dataset + Distribution + Acquisition via "
    "IngestScan. Never triggered off the translator terminal itself; a "
    "periodic reconciliation sweep against the read model. Not a control "
    "path: it never drives the substrate, only records the file a "
    "promoted capture already produced."
)


# Sentinel model ref: CaptureScanIngestor is rule-based, not an LLM agent.
# The Agent aggregate requires a ModelRef; this value is never used to
# build an LLM (no subscriber / no build_llm call for this agent).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:CaptureScanIngestor:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000014650012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000014650013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000014650014")


async def seed_capture_scan_ingestor_agent(kernel: Kernel) -> None:
    """Seed the CaptureScanIngestor Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAPTURE_SCAN_INGESTOR_AGENT_ID,
        name=CAPTURE_SCAN_INGESTOR_AGENT_NAME,
        kind=CAPTURE_SCAN_INGESTOR_AGENT_KIND,
        version=CAPTURE_SCAN_INGESTOR_AGENT_VERSION,
        description=CAPTURE_SCAN_INGESTOR_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCaptureScanIngestorAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAPTURE_SCAN_INGESTOR_AGENT_DESCRIPTION",
    "CAPTURE_SCAN_INGESTOR_AGENT_ID",
    "CAPTURE_SCAN_INGESTOR_AGENT_KIND",
    "CAPTURE_SCAN_INGESTOR_AGENT_NAME",
    "CAPTURE_SCAN_INGESTOR_AGENT_VERSION",
    "seed_capture_scan_ingestor_agent",
]
