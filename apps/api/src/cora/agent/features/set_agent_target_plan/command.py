"""The `SetAgentTargetPlan` command -- intent dataclass for this slice.

Sets (or clears) the recipe Plan an autonomous agent starts for each ready
Subject. PUT semantics: the supplied `target_plan_id` IS the post-set target;
None clears it. No cross-BC Plan-existence check (eventual-consistency stance,
mirroring StartRun.decided_by_decision_id).

The setting actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SetAgentTargetPlan:
    """Set or clear an autonomous Agent's target Plan (PUT semantics)."""

    agent_id: UUID
    target_plan_id: UUID | None
