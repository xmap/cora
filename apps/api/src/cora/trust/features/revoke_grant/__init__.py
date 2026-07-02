"""Vertical slice for the `RevokeGrant` command.

Module-as-namespace surface, symmetric with the other Trust slices:

    from cora.trust.features import revoke_grant

    cmd = revoke_grant.RevokeGrant(
        policy_id=..., principal_id=..., reason="agent decommissioned"
    )
    handler = revoke_grant.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

First-class authority revocation: removes one principal's grant from a
Policy's permitted set. Set-membership silently idempotent (revoking an
absent principal emits no event); the only rejection is
`PolicyNotFoundError` (HTTP 404) when the Policy does not exist.

Single-stream (NOT cross-BC): this slice writes only `PolicyGrantRevoked`
on the Policy stream. The mid-run compensation that HOLDS the revoked
principal's in-flight runs is a separate, eventually-consistent
subscriber reacting to the committed event, per the compensation-slice
no-cascade lock. The 6th compensation slice; the 2nd set-membership
variant after `revoke_tool_from_agent`.
"""

from cora.trust.features.revoke_grant import tool
from cora.trust.features.revoke_grant.command import RevokeGrant
from cora.trust.features.revoke_grant.decider import decide
from cora.trust.features.revoke_grant.handler import Handler, bind
from cora.trust.features.revoke_grant.route import router

__all__ = [
    "Handler",
    "RevokeGrant",
    "bind",
    "decide",
    "router",
    "tool",
]
