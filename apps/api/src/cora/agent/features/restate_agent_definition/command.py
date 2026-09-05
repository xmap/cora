"""The `RestateAgentDefinition` command -- intent dataclass for this slice.

Restates an existing Agent's name and/or brain on its own stream. Events are
INSERT-only, so a stream written before `brain` existed cannot be rewritten to
carry one; this appends the correction instead.

Both fields are optional and at least one must be set. A field left None means
UNCHANGED, not cleared: neither a name nor a brain has a meaningful empty
value, so there is nothing for a clear to mean.

`reason` is required. Appending to an append-only governance record is an act
someone chooses, and the record should say why.

The restating actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.agent.aggregates.agent import BrainRef


@dataclass(frozen=True)
class RestateAgentDefinition:
    """Restate an existing Agent's name and/or brain (both optional, one required)."""

    agent_id: UUID
    reason: str
    name: str | None = None
    brain: BrainRef | None = None
