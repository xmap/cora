"""Pure decider for the `DefinePolicy` command.

Pure function: given the current Policy state (None for a fresh
stream) and a `DefinePolicy` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler.

Does NOT verify that `conduit_id` references an existing Conduit or
that each `permitted_principal_ids` UUID corresponds to a registered
Actor — see `cora.trust.aggregates.policy.state` for the eventual-
consistency rationale.

Grants are converted to a sorted tuple of `(UUID, str)` pairs for the
event payload (events carry primitives; `to_payload` serializes each
pair as a two-element array).
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.policy import (
    InvalidPolicySurfaceError,
    Policy,
    PolicyAlreadyExistsError,
    PolicyDefined,
    PolicyName,
)
from cora.trust.features.define_policy.command import DefinePolicy


def decide(
    state: Policy | None,
    command: DefinePolicy,
    *,
    now: datetime,
    new_id: UUID,
) -> list[PolicyDefined]:
    """Decide the events produced by defining a new policy.

    Invariants:
      - State must be None (defensive AlreadyExists guard against
        UUID collision) -> PolicyAlreadyExistsError
      - surface_id must bind a real Surface, not the nil sentinel
        -> InvalidPolicySurfaceError
      - Name must be valid -> InvalidPolicyNameError
        (via PolicyName VO)
    """
    if state is not None:
        raise PolicyAlreadyExistsError(state.id)
    if command.surface_id == NIL_SENTINEL_ID:
        raise InvalidPolicySurfaceError
    name = PolicyName(command.name)  # validates + trims
    return [
        PolicyDefined(
            policy_id=new_id,
            name=name.value,
            conduit_id=command.conduit_id,
            grants=tuple(sorted(command.grants)),
            occurred_at=now,
            surface_id=command.surface_id,
        )
    ]
