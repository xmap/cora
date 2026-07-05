"""Ratification aggregate: state, errors, events, evolver, read repo.

The consequence gate's aggregate: the co-signature record that a consequential
action is awaiting, or has received, a second independent principal's approval.
Vertical slices live under `cora.trust.features.<verb>_ratification/` and import
state + event types from here.

3-state FSM: Requested -> Granted | Denied. `Requested` is genesis; both others
are terminal. The independence invariant (grantor/denier must differ from the
requester) is the four-eyes property the gate provides. Lands DORMANT: nothing
gates on it yet.
"""

from cora.trust.aggregates.ratification.events import (
    RatificationDenied,
    RatificationEvent,
    RatificationGranted,
    RatificationRequested,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.ratification.evolver import evolve, fold
from cora.trust.aggregates.ratification.read import load_ratification
from cora.trust.aggregates.ratification.state import (
    CONSEQUENCE_CLASS_MAX_LENGTH,
    InvalidConsequenceClassError,
    InvalidRatificationReasonError,
    Ratification,
    RatificationAlreadyExistsError,
    RatificationCannotDenyError,
    RatificationCannotGrantError,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
)

__all__ = [
    "CONSEQUENCE_CLASS_MAX_LENGTH",
    "InvalidConsequenceClassError",
    "InvalidRatificationReasonError",
    "Ratification",
    "RatificationAlreadyExistsError",
    "RatificationCannotDenyError",
    "RatificationCannotGrantError",
    "RatificationDenied",
    "RatificationEvent",
    "RatificationGranted",
    "RatificationNotFoundError",
    "RatificationRequested",
    "RatificationRequesterCannotSelfRatifyError",
    "RatificationStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_ratification",
    "to_payload",
]
