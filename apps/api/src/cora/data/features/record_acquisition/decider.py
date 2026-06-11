"""Pure decider for the `RecordAcquisition` command.

Pure function: given the (always None) Acquisition state, a
`RecordAcquisition` command, and a pre-loaded
`AcquisitionRecordingContext`, returns the events to append. No I/O,
no awaits, no side effects.

`now` (the CORA-side recording wall-clock), `new_id`, `recorded_by`,
and `skew_tolerance` are injected by the application handler from the
Clock / IdGenerator ports and the envelope principal.

## Decider invariant ordering (pinned, design lock L14)

  1. Pydantic 422 boundary parse-shape (off-decider).
  2. Authorize -> UnauthorizedError (handler, BEFORE any reads).
  3. Defensive shape re-checks: InvalidAcquisitionSettingsError /
     InvalidAcquisitionEvidenceError / InvalidAcquisitionCapturedAtError.
  4. Genesis stream-empty guard -> AcquisitionAlreadyExistsError.
  5. Handler-side Dataset pre-load -> DatasetNotFoundError.
  6. Handler-side Asset lookup -> AcquisitionAssetNotFoundError (None).
  7. Capturing-affordance gate -> AcquisitionCannotRecordWithoutCapturingError.
  8. Handler-side Run pre-load (only if producing_run_id is not None)
     -> AcquisitionRunNotFoundError.
  9. Emit AcquisitionRecorded.

Steps 2, 5, 6, 8 are enforced by the handler (it raises before
building the context). The decider re-states the context contract via
assertion-style guards (defensive, never fire if the handler is
correct), runs the shape re-checks (3), the genesis guard (4), and
the Capturing gate (7), then emits.

The Capturing affordance value is compared as the literal string
`"Capturing"` (the port surfaces `frozenset[str]`, not the typed
Equipment BC enum, to keep the port BC-import-free).
"""

from datetime import datetime, timedelta
from uuid import UUID

from cora.data.aggregates.acquisition import (
    AcquisitionAlreadyExistsError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionRecorded,
    InvalidAcquisitionCapturedAtError,
    validate_evidence,
    validate_settings,
)
from cora.data.aggregates.acquisition.state import Acquisition
from cora.data.features.record_acquisition.command import RecordAcquisition
from cora.data.features.record_acquisition.context import AcquisitionRecordingContext
from cora.shared.identity import ActorId

# The Capturing affordance value string. Compared as a literal because
# the AssetLookup port surfaces affordances as `frozenset[str]` (no
# Equipment BC import). Mirrors the enum value `Affordance.CAPTURING`.
_CAPTURING_AFFORDANCE = "Capturing"

# Default clock-skew tolerance for the captured_at upper-bound check.
# captured_at may legitimately precede recorded_at by any amount
# (backfills); only a future captured_at beyond recorded_at + this
# bound is rejected. The handler supplies the value so the decider
# stays pure; this constant is the default.
DEFAULT_CAPTURED_AT_SKEW_TOLERANCE = timedelta(seconds=60)


def decide(
    state: Acquisition | None,
    command: RecordAcquisition,
    *,
    context: AcquisitionRecordingContext,
    now: datetime,
    new_id: UUID,
    recorded_by: ActorId,
    skew_tolerance: timedelta = DEFAULT_CAPTURED_AT_SKEW_TOLERANCE,
) -> list[AcquisitionRecorded]:
    """Decide the events produced by recording a new Acquisition.

    Invariants:
      - State must be None (genesis-only) -> AcquisitionAlreadyExistsError
      - settings must be primitive-leaf shaped
        -> InvalidAcquisitionSettingsError
      - evidence must be primitive-leaf shaped
        -> InvalidAcquisitionEvidenceError
      - captured_at must be tz-aware and not in the future beyond
        now + skew_tolerance -> InvalidAcquisitionCapturedAtError
      - The producing Asset's Family must declare Capturing
        -> AcquisitionCannotRecordWithoutCapturingError
    """
    if state is not None:
        raise AcquisitionAlreadyExistsError(state.id)

    # Defensive shape re-checks (Pydantic catches most at the route).
    settings = validate_settings(command.settings)
    evidence = validate_evidence(command.evidence)
    captured_at = _validate_captured_at(command.captured_at, now=now, skew_tolerance=skew_tolerance)

    # Capturing-affordance gate: the sole write-time cross-BC business
    # invariant. The handler has already proven the Asset exists
    # (context.asset is non-None) and pre-loaded its affordance set.
    if _CAPTURING_AFFORDANCE not in context.asset.family_affordances:
        raise AcquisitionCannotRecordWithoutCapturingError(command.producing_asset_id)

    return [
        AcquisitionRecorded(
            acquisition_id=new_id,
            dataset_id=command.dataset_id,
            producing_asset_id=command.producing_asset_id,
            producing_run_id=command.producing_run_id,
            captured_at=captured_at,
            settings=settings,
            evidence=evidence,
            occurred_at=now,
            recorded_by=recorded_by,
        )
    ]


def _validate_captured_at(
    captured_at: datetime,
    *,
    now: datetime,
    skew_tolerance: timedelta,
) -> datetime:
    """Validate captured_at: tz-aware and not absurdly in the future.

    captured_at MAY precede now by any amount (backfills from offline
    acquisition hosts, post-hoc reprocessor registration). Only the
    upper bound (now + skew_tolerance) is enforced, for clock-skew
    safety, not the broader ordering invariant.
    """
    if captured_at.tzinfo is None:
        raise InvalidAcquisitionCapturedAtError("captured_at must be timezone-aware")
    if captured_at > now + skew_tolerance:
        raise InvalidAcquisitionCapturedAtError(
            "captured_at is in the future beyond the clock-skew tolerance "
            f"(captured_at={captured_at.isoformat()}, "
            f"now={now.isoformat()}, tolerance={skew_tolerance})"
        )
    return captured_at
