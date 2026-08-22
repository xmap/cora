"""Bootstrap-time seed for the DurableCopyRegistrar Agent.

The durable-distribution sweep runtime (`cora.api._durable_distribution`)
needs an Agent record (and its co-registered Actor) to exist at the
pinned `DURABLE_COPY_REGISTRAR_AGENT_ID` so it can issue
`RegisterDistribution` as an agent-kind principal when it finds a
Dataset whose durable copy is unrecorded. Mirrors
`cora.agent.seed_capture_scan_ingestor.seed_capture_scan_ingestor_agent`
verbatim except for the per-agent constants below; the shared
scaffolding lives in `cora.agent._agent_seed`.

  - Pinned UUID opens a NEW numeric-mnemonic block, `2679` (`COPY` on a
    phone keypad; verified unclaimed against the 17 blocks already in
    use). Deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`). The sweep is a poll-and-append loop,
    not an LLM subscriber.
  - A SEPARATE principal from CaptureScanIngestor and every other seeded
    agent, deliberately: an operator can revoke the `RegisterDistribution`
    grant this agent needs without blinding the scan ingestor or any
    other automated writer, and `Distribution.registered_by` tells this
    runtime's writes apart from a human operator's own
    `register_distribution` calls in the record.
  - Authorization: the sweep issues exactly one command,
    `RegisterDistribution`, through the Authorize port like any
    principal. Under TrustAuthorize the operator's configured Policy
    must include this principal + `{RegisterDistribution}`. Without the
    grant, a real sweep tick logs `durable_distribution.register_unauthorized`
    and stops the tick (see `cora.api._durable_distribution_driver`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# DurableCopyRegistrar agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `CAPTURE_SCAN_INGESTOR_AGENT_ID`: changing this orphans every prior
# durable-copy Distribution's `registered_by` pointer. UUID opens a new
# numeric-mnemonic block, `2679` (COPY).
DURABLE_COPY_REGISTRAR_AGENT_ID = UUID("01900000-0000-7000-8000-000026790010")
DURABLE_COPY_REGISTRAR_AGENT_NAME = "DurableCopyRegistrar"
DURABLE_COPY_REGISTRAR_AGENT_KIND = "DurableCopyRegistrar"
DURABLE_COPY_REGISTRAR_AGENT_VERSION = "1.0.0"
DURABLE_COPY_REGISTRAR_AGENT_DESCRIPTION = (
    "Deterministic in-process runtime: sweeps Datasets whose durable "
    "copy (the archival tier an operator later copies the experiment "
    "to) has not been recorded yet, and registers it as a second "
    "Distribution on the same Dataset via RegisterDistribution. Never "
    "triggered off the originating scan itself; a periodic "
    "reconciliation sweep against the read model. Not a control path: "
    "it never drives the substrate, only records a byte-copy an "
    "operator already made."
)


# Sentinel model ref: DurableCopyRegistrar is rule-based, not an LLM agent.
# The Agent aggregate requires a ModelRef; this value is never used to
# build an LLM (no subscriber / no build_llm call for this agent).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:DurableCopyRegistrar:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000026790012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000026790013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000026790014")


async def seed_durable_copy_registrar_agent(kernel: Kernel) -> None:
    """Seed the DurableCopyRegistrar Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=DURABLE_COPY_REGISTRAR_AGENT_ID,
        name=DURABLE_COPY_REGISTRAR_AGENT_NAME,
        kind=DURABLE_COPY_REGISTRAR_AGENT_KIND,
        version=DURABLE_COPY_REGISTRAR_AGENT_VERSION,
        description=DURABLE_COPY_REGISTRAR_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedDurableCopyRegistrarAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "DURABLE_COPY_REGISTRAR_AGENT_DESCRIPTION",
    "DURABLE_COPY_REGISTRAR_AGENT_ID",
    "DURABLE_COPY_REGISTRAR_AGENT_KIND",
    "DURABLE_COPY_REGISTRAR_AGENT_NAME",
    "DURABLE_COPY_REGISTRAR_AGENT_VERSION",
    "seed_durable_copy_registrar_agent",
]
