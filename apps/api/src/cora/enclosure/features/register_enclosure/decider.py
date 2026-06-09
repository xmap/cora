"""Pure decider for the `RegisterEnclosure` command.

Pure function: given the current Enclosure state (None for a fresh
stream) and a `RegisterEnclosure` command, returns the events to
append. No I/O, no awaits, no side effects.

`now`, `new_id`, and `registered_by` are injected by the application
handler from the Clock and IdGenerator ports and from the route /
tool boundary (the non-determinism principle: capture, don't
recompute). Registration is operator-only today; `registered_by` is
typed `ActorId` directly, not the trigger-aware union, matching the
genesis-event payload shape in `cora.enclosure.aggregates.enclosure`.

## Validation

  - State must be None (genesis-only) -> `EnclosureAlreadyExistsError`
  - `name` is wrapped via `EnclosureName(...)` which validates 1-200
    chars in `__post_init__` -> `InvalidEnclosureNameError`.

`containing_asset_id` is a bare cross-BC opaque `UUID` pointer. Per
the locked design the decider stays pure: cross-aggregate existence
checks (AssetLookup) are deferred to the handler layer pending walk-
cost evidence, and are not added here to preserve the
`cora.infrastructure.ports` no-cross-BC-dependency invariant.

Initial permit-status is implicit `Unknown` and initial lifecycle is
implicit `Active`; the evolver seeds both from the genesis event
type. Per the universal industrial + cloud-native consensus on
registration-time defaults (Tango UNKNOWN, EPICS UDF, Azure Resource
Health Unknown, k8s Pending).

Cross-stream uniqueness of the `(containing_asset_id, name)` address
tuple is NOT enforced here: the decider cannot see other Enclosure
streams without DCB. The projection's partial UNIQUE INDEX (active
rows only) is the cross-stream guard; this decider's pre-state-None
check is the genesis collision guard against same-stream double
registration.
"""

from datetime import datetime

from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureAlreadyExistsError,
    EnclosureId,
    EnclosureName,
    EnclosureRegistered,
)
from cora.enclosure.features.register_enclosure.command import RegisterEnclosure
from cora.shared.identity import ActorId


def decide(
    state: Enclosure | None,
    command: RegisterEnclosure,
    *,
    now: datetime,
    new_id: EnclosureId,
    registered_by: ActorId,
) -> list[EnclosureRegistered]:
    """Decide the events produced by registering a new Enclosure.

    Invariants:
      - State must be None (genesis-only)
        -> EnclosureAlreadyExistsError
      - Name must be valid -> InvalidEnclosureNameError
        (via EnclosureName VO)

    `registered_by` is the operator's `ActorId` (registration is
    always operator-driven; no Monitor or Auto counterpart). Folded
    onto the event payload as the fold-symmetric genesis attribution
    per [[project_fold_symmetry_design]].
    """
    if state is not None:
        raise EnclosureAlreadyExistsError(state.id)

    name = EnclosureName(command.name)

    return [
        EnclosureRegistered(
            enclosure_id=new_id,
            name=name.value,
            containing_asset_id=command.containing_asset_id,
            registered_by=registered_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
