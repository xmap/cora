"""Translate an Agent's declared model identity into the LLM port's shape.

Two `ModelRef` dataclasses exist with the same three fields, and the
duplication is deliberate: the aggregate VO carries write-time domain
invariants (trim, length caps, `InvalidModelRefError`) because callers
supply it through `define_agent`, while the port's is the wire shape the
adapter consumes. `cora.infrastructure.ports.llm.ModelRef` documents the
split and names this per-call translation as the intended seam.

It says the subscriber does this. For a long time nothing did. Both debrief
call sites built their request from a module-level default instead, so the
Agent's declaration was inert and the catalog gate that `define_agent`
applies to it governed nothing about the call it was supposed to govern.
The two agreed only because the Agent seed set its model from that same
default, which is agreement by construction rather than by check.

The declaration now lives on `Agent.brain` rather than in the legacy
`model_ref` slot, so this seam reads the brain. Reading the old slot would
reintroduce the same inertness by a different route: it is empty for every
Agent defined since the seeds moved over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent.aggregates.agent import BrainKind, InvalidAgentBrainKindError
from cora.infrastructure.ports.llm import ModelRef as PortModelRef

if TYPE_CHECKING:
    from cora.agent.aggregates.agent import BrainRef


def to_port_model_ref(brain: BrainRef | None) -> PortModelRef:
    """Carry an Agent's declared model across to the port unchanged.

    Takes the brain rather than the legacy `model_ref` slot, because that
    slot is empty for every Agent defined since the seeds moved over, and a
    caller reading it would serve the module default while believing it was
    serving the Agent's declaration.

    No validation of the values here. They were already checked at
    `define_agent`, and re-checking would put the invariant in two places.
    What IS checked is the kind: an LLM call to an Agent whose brain is a
    rule has no model to name, and inventing one would put a model the
    catalog never approved behind a real Agent's identity. The evolver never
    produces state without a brain, so `None` means a caller built an Agent
    by hand and skipped it.
    """
    if brain is None or brain.kind is not BrainKind.LANGUAGE_MODEL:
        raise InvalidAgentBrainKindError(brain.kind.value if brain is not None else None)
    assert brain.model_ref is not None  # guaranteed by BrainRef.__post_init__
    return PortModelRef(
        provider=brain.model_ref.provider,
        model=brain.model_ref.model,
        snapshot_pin=brain.model_ref.snapshot_pin,
    )


__all__ = ["to_port_model_ref"]
