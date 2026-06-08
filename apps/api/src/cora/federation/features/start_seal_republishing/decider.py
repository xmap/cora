"""Pure decider for the `StartSealRepublishing` command.

Single-source transition: `Live -> Republishing`. Strict-not-
idempotent (matches the Credential rotation / Permit transition
precedents): starting republishing against an already Republishing
Seal raises `SealCannotStartRepublishingError`.

`started_by` is handler-injected from the request envelope's
`principal_id` per the non-determinism principle (capture, don't
recompute). The decider is pure: state + command + injected
non-determinism in, events out.

## Validation

  - State must not be None (Seal must exist)
    -> SealNotFoundError
  - Current status must be `Live`
    -> SealCannotStartRepublishingError

`reason` on the command flows through to the emitted
`SealRepublishingStarted` event payload so operator context survives
on the immutable event log.
"""

from datetime import datetime

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealRepublishingStarted,
    SealStatus,
)
from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)
from cora.shared.identity import ActorId


def decide(
    state: Seal | None,
    command: StartSealRepublishing,
    *,
    now: datetime,
    started_by: ActorId,
) -> list[SealRepublishingStarted]:
    """Decide the events produced by starting republishing on a Live Seal.

    Invariants:
      - State must not be None -> SealNotFoundError
      - Current status must be Live -> SealCannotStartRepublishingError
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.LIVE:
        raise SealCannotStartRepublishingError(state.facility_id, state.status)

    return [
        SealRepublishingStarted(
            facility_id=state.facility_id,
            started_by=started_by,
            occurred_at=now,
            reason=command.reason,
        )
    ]


__all__ = ["decide"]
