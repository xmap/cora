"""The `RevokePolicyGrant` command: intent dataclass for this slice.

`policy_id` is the target Policy aggregate. `permitted_principal_id` is the grant
being removed: the principal whose entry is dropped from the Policy's
`permitted_principal_ids` allow-list (the field name ties directly to that state
field, so it is not confused with the invoker). `reason` is REQUIRED operator free
text; it rides the `PolicyGrantRevoked` event so operator context survives on the
immutable event log, and it feeds the downstream mid-run compensation Decision.

The invoker's principal id is supplied separately by the application handler at
call time (its `principal_id` kwarg) and stamped onto the event as `revoked_by`.
The command carries only the grant being removed, never the invoker.

Command class carries the aggregate qualifier (`RevokePolicyGrant`) because it
acts on a per-aggregate sub-concept (a grant = one allow-list entry); the slice
directory and MCP tool drop it (`revoke_grant`), per the sub-concept naming rule.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RevokePolicyGrant:
    """Revoke one principal's grant from a Policy.

    Removes `permitted_principal_id` from `Policy.permitted_principal_ids`.
    Silently idempotent: a no-op when the principal is already absent. `reason`
    is required (1-REASON_MAX_LENGTH chars, validated at the API boundary and
    defensively at the decider).
    """

    policy_id: UUID
    permitted_principal_id: UUID
    reason: str
