"""The `RevokeGrant` command: intent dataclass for this slice.

`policy_id` is the target Policy aggregate. `principal_id` is the grant
being removed: the principal whose entry is dropped from the Policy's
`permitted_principal_ids` allow-list. `reason` is REQUIRED operator free
text captured at the API boundary (for example, "agent decommissioned",
"credential compromise", "role change") and flows onto the emitted
`PolicyGrantRevoked` event so operator context survives on the immutable
event log; it also feeds the downstream mid-run compensation Decision.

The invoker's principal-id is supplied separately by the application
handler at call time and stamped onto the event as `revoked_by`.

Set-membership, silently idempotent: revoking a principal that is not in
the Policy's permitted set is a no-op (no event) rather than an error,
mirroring `revoke_tool_from_agent`. The only rejection is
`PolicyNotFoundError` when the Policy itself does not exist.

Naming note: the field is `principal_id` (the grant to revoke), distinct
from the invoker's `principal_id` handler kwarg. The command carries the
target; the handler carries the actor.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RevokeGrant:
    """Operator revokes one principal's grant from a Policy.

    Removes `principal_id` from `Policy.permitted_principal_ids`. Silently
    idempotent: a no-op when the principal is already absent. `reason` is
    required (1-`REASON_MAX_LENGTH` chars, validated at the API boundary
    and defensively at the decider).
    """

    policy_id: UUID
    principal_id: UUID
    reason: str
