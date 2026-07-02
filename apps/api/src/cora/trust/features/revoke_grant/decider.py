"""Pure decider for the `RevokeGrant` command.

Set-membership removal: drops one principal from the Policy's
`permitted_principal_ids` allow-list. This is the 6th compensation slice
and the 2nd set-membership variant (after `revoke_tool_from_agent`), so
it is SILENTLY IDEMPOTENT: revoking a principal that is not in the
permitted set returns `[]` (no event), not an error. There is NO
`PolicyCannotRevokeGrantError` / 409, because Policy has no status FSM to
transition, and the security-meaningful end-state ("this principal is not
authorized") is already true when the principal is absent.

`revoked_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`PolicyGrantRevoked` event for the audit denorm.

Symmetric by construction: `command.principal_id` is a bare UUID, so
revoking a human's grant and an autonomous agent's grant run the same
code path with no actor-kind branch (paper invariant I1).

## Validation

  - State must not be None (Policy must exist)
    -> PolicyNotFoundError
  - Reason must be 1-REASON_MAX_LENGTH chars after trim
    -> InvalidPolicyGrantRevokeReasonError
  - Principal not in permitted set -> no event ([]), silently idempotent
"""

from datetime import datetime
from uuid import UUID

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.policy import (
    InvalidPolicyGrantRevokeReasonError,
    Policy,
    PolicyGrantRevoked,
    PolicyNotFoundError,
)
from cora.trust.features.revoke_grant.command import RevokeGrant


def decide(
    state: Policy | None,
    command: RevokeGrant,
    *,
    now: datetime,
    revoked_by: UUID,
) -> list[PolicyGrantRevoked]:
    """Decide the events produced by revoking a principal's grant.

    Invariants:
      - State must not be None -> PolicyNotFoundError
      - Reason must be 1-REASON_MAX_LENGTH chars after trim
        -> InvalidPolicyGrantRevokeReasonError
      - Principal not in permitted set -> [] (silently idempotent)
    """
    if state is None:
        raise PolicyNotFoundError(command.policy_id)

    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidPolicyGrantRevokeReasonError(command.reason)

    if command.principal_id not in state.permitted_principal_ids:
        return []

    return [
        PolicyGrantRevoked(
            policy_id=state.id,
            revoked_principal_id=command.principal_id,
            revoked_by=revoked_by,
            reason=trimmed,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
