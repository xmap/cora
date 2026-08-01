"""The `DeprecateAgent` command -- intent dataclass for this slice.

Deprecates an Agent (Defined or Versioned). Terminal: deprecated
Agents cannot be revived. `reason` is a closed
required a closed `DeprecationReason` (Superseded / Defective / Obsolete).

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
