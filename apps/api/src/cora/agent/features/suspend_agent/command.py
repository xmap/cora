"""The `SuspendAgent` command -- intent dataclass for this slice.

Pauses a `Versioned` Agent. Non-terminal: returns via
`resume_agent`. `reason` is REQUIRED (1-500 chars after trim);
mirrors the shared `REASON_MAX_LENGTH` bound.

The suspending actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SuspendAgent:
    """Suspend an Agent (`Versioned -> Suspended`)."""

    agent_id: UUID
    reason: str
