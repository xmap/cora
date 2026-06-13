"""Policy aggregate: state, errors, events, evolver, read repo, pure evaluate.

Vertical slices that operate on this aggregate live under
`cora.trust.features.<verb>_policy/` and import from here for state
and event types. The pure `evaluate` function is the domain-level
Policy Decision Point used by both the `evaluate_policy` query
slice (3d) and the `TrustAuthorize` adapter (3e).
"""

from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    PolicyEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.policy.evolver import evolve, fold
from cora.trust.aggregates.policy.read import load_policy
from cora.trust.aggregates.policy.state import (
    POLICY_NAME_MAX_LENGTH,
    InvalidPolicyNameError,
    InvalidPolicySurfaceError,
    Policy,
    PolicyAlreadyExistsError,
    PolicyName,
    evaluate,
)

__all__ = [
    "POLICY_NAME_MAX_LENGTH",
    "InvalidPolicyNameError",
    "InvalidPolicySurfaceError",
    "Policy",
    "PolicyAlreadyExistsError",
    "PolicyDefined",
    "PolicyEvent",
    "PolicyName",
    "evaluate",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_policy",
    "to_payload",
]
