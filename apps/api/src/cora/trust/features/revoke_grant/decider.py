"""Pure decider for the `RevokePolicyGrant` command.

Set-membership removal: drops one principal from the Policy's
`permitted_principal_ids` allow-list. This is a set-membership variant (like
`revoke_tool_from_agent`), so it is SILENTLY IDEMPOTENT: revoking a principal
that is not in the permitted set returns `[]` (no event), not an error. There is
NO `PolicyCannotRevokeGrantError` / 409, because Policy has no status FSM to guard.

`revoked_by` is threaded in by the handler from the request envelope's
principal_id, and stamped onto the `PolicyGrantRevoked` event for the audit
denorm. Kind-blind: revoking a human's grant and an autonomous agent's grant run
the same code; the decider compares bare principal identifiers and never reads
actor kind.
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
from cora.trust.features.revoke_grant.command import RevokePolicyGrant


def decide(
    state: Policy | None,
    command: RevokePolicyGrant,
    *,
    revoked_by: UUID,
    now: datetime,
) -> list[PolicyGrantRevoked]:
    """Decide the events produced by revoking a grant.

    Invariants:
      - State must not be None (Policy must exist) -> PolicyNotFoundError
      - Reason 1-REASON_MAX_LENGTH chars after trim
        -> InvalidPolicyGrantRevokeReasonError
      - Principal not in the permitted set -> no event ([]), silently idempotent

    No self-lockout or last-grant guard: a principal MAY revoke its own grant,
    and the final grant MAY be revoked (leaving a deny-all Policy). This is
    intentional for the kill-switch, whose whole point is to remove a principal's
    authority; recovery is a fresh grant via define_policy, not a guard here.

    Ordering (reason-validation BEFORE the membership no-op) is deliberate: reason
    is a required bounded command field, so a malformed command is rejected even
    when the target happens to be absent, closing a validation-bypass path.
    """
    if state is None:
        raise PolicyNotFoundError(command.policy_id)
    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidPolicyGrantRevokeReasonError(command.reason)
    if command.permitted_principal_id not in state.permitted_principal_ids:
        return []
    return [
        PolicyGrantRevoked(
            policy_id=state.id,
            principal_id=command.permitted_principal_id,
            revoked_by=revoked_by,
            reason=trimmed,
            occurred_at=now,
        )
    ]
