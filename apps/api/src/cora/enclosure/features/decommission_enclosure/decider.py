"""Pure decider for the `DecommissionEnclosure` command.

Terminal transition: `lifecycle=Active -> Decommissioned`. Strict-not-
idempotent: re-decommissioning an already-Decommissioned enclosure
raises `EnclosureCannotDecommissionError` (HTTP 409) per the
`decommission_facility` / `deregister_supply` convention.

`triggered_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`EnclosureDecommissioned` event for the fold-symmetric terminal
attribution pair (`decommissioned_at=occurred_at, decommissioned_by=
triggered_by`) per [[project_fold_symmetry_design]].

`permit_status` is preserved untouched across decommission as audit
trail per the two-axis orthogonality lock in
[[project_enclosure_stage1_design]]: the lifecycle axis terminates
without mutating the operational permit axis. The evolver only folds
`lifecycle`, `decommissioned_at`, and `decommissioned_by`.

`reason` is validated via the `EnclosureReason` VO (trimmed, bounded
1-500 chars); the trimmed value flows to the event payload as a bare
string mirroring the `SupplyReason` / `EnclosurePermitObserved`
precedent.

## Validation

  - State must not be None (enclosure must exist)
    -> `EnclosureNotFoundError`
  - Current lifecycle must be Active (not Decommissioned)
    -> `EnclosureCannotDecommissionError`
  - Reason must be valid 1-500 trimmed chars
    -> `InvalidEnclosureReasonError` (via `EnclosureReason` VO)
"""

from datetime import datetime

from cora.enclosure.aggregates._value_types import EnclosureReason
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureCannotDecommissionError,
    EnclosureDecommissioned,
    EnclosureLifecycle,
    EnclosureNotFoundError,
)
from cora.enclosure.features.decommission_enclosure.command import (
    DecommissionEnclosure,
)
from cora.shared.identity import ActorId


def decide(
    state: Enclosure | None,
    command: DecommissionEnclosure,
    *,
    now: datetime,
    triggered_by: ActorId,
) -> list[EnclosureDecommissioned]:
    """Decide the events produced by decommissioning an Enclosure.

    Invariants:
      - State must not be None -> EnclosureNotFoundError
      - Current lifecycle must be Active
        -> EnclosureCannotDecommissionError
      - Reason must be valid -> InvalidEnclosureReasonError
        (via EnclosureReason VO)

    `triggered_by` is the operator's `ActorId`. Decommission is
    operator-only per [[project_enclosure_stage1_design]]; no Monitor
    or Auto counterpart (no substream or timer should ever auto-
    decommission an Enclosure).
    """
    if state is None:
        raise EnclosureNotFoundError(command.enclosure_id)
    if state.lifecycle is EnclosureLifecycle.DECOMMISSIONED:
        raise EnclosureCannotDecommissionError(state.id)

    reason = EnclosureReason(command.reason)

    return [
        EnclosureDecommissioned(
            enclosure_id=state.id,
            reason=reason.value,
            triggered_by=triggered_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
