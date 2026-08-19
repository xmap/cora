"""Translate an Agent's declared model identity into the LLM port's shape.

Two `ModelRef` dataclasses exist with the same three fields, and the
duplication is deliberate: the aggregate VO carries write-time domain
invariants (trim, length caps, `InvalidModelRefError`) because callers
supply it through `define_agent`, while the port's is the wire shape the
adapter consumes. `cora.infrastructure.ports.llm.ModelRef` documents the
split and names this per-call translation as the intended seam.

It says the subscriber does this. Until now nothing did. Both debrief
call sites built their request from a module-level default instead, so
`Agent.model_ref` was inert and the catalog gate that `define_agent`
applies to it governed nothing about the call it was supposed to
govern. The two agreed only because the Agent seed sets its `model_ref`
from that same default, which is agreement by construction rather than
by check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.ports.llm import ModelRef as PortModelRef

if TYPE_CHECKING:
    from cora.agent.aggregates.agent import ModelRef as AgentModelRef


def to_port_model_ref(model_ref: AgentModelRef) -> PortModelRef:
    """Carry an Agent's declared identity across to the port unchanged.

    No validation here. The values were already checked at
    `define_agent`, and re-checking would put the invariant in two
    places.
    """
    return PortModelRef(
        provider=model_ref.provider,
        model=model_ref.model,
        snapshot_pin=model_ref.snapshot_pin,
    )


__all__ = ["to_port_model_ref"]
