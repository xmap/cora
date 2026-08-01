"""The `DeprecateAgent` command -- intent dataclass for this slice.

Deprecates an Agent (Defined or Versioned). Terminal: deprecated
Agents cannot be revived. `reason` is a closed
operator-supplied explanation (1-500 chars after trim if provided).

The deprecating actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateAgent:
    """Deprecate an Agent (`Defined | Versioned -> Deprecated`)."""

    agent_id: UUID
    reason: DeprecationReason
