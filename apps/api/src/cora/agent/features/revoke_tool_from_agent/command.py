"""The `RevokeToolFromAgent` command -- intent dataclass for this slice.

Removes one MCP `tool_name` from the Agent's per-agent allowlist.
Idempotent: revoking a tool the Agent doesn't have emits NO event.

The revoking actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RevokeToolFromAgent:
    """Revoke one MCP tool from an Agent."""

    agent_id: UUID
    tool_name: str
    reason: str
