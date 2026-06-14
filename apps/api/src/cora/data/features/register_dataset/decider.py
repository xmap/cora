"""Pure decider for the `RegisterDataset` command.

Pure function: given the (always None) Dataset state, a
`RegisterDataset` command, and a pre-loaded
`DatasetRegistrationContext`, returns the events to append. No
I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Cross-aggregate validation (gate-review Q2 lock B + 7b status check)

Existence-only checks for Run + Subject; existence + non-Discarded
status check for derived_from sources. The decider trusts the
handler's loads. Specifically:

  - If `command.producing_run_id` is set, `context.producing_run`
    must be non-None (handler raises `ProducingRunNotFoundError`
    upstream if the Run doesn't exist; this branch validates the
    handler's contract was honoured).
  - If `command.subject_id` is set, `context.subject` must be
    non-None (same shape).
  - For each id in `command.derived_from`, `context.derived_from`
    must contain it AND its status must NOT be `Discarded` (we
    don't allow new lineage edges into bytes that no longer exist).

No status checks for Run / Subject (Datasets register against any
Run state, against any Subject state). Discarded-status check only
applies to derived_from lineage sources (7b tightening).

Per the precedent set by `start_run`'s decider, defensive guards
on context.* alignment are assertions of the handler's contract,
not user-facing validations. If the handler is correct, they
never fire.

## VO trim semantics

Field VOs (`DatasetName`, `DatasetUri`, `DatasetChecksum`,
`DatasetEncoding`) handle their own trimming + validation in
`__post_init__`; the on-the-wire payload carries the trimmed
values (so the persisted event payload is canonical).
"""

from datetime import datetime
from uuid import UUID

from cora.data.aggregates.dataset import (
    DatasetAlreadyExistsError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetRegistered,
    DatasetStatus,
    DatasetUri,
    DerivedFromDatasetsDiscardedError,
    DerivedFromDatasetsNotFoundError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
    validate_byte_size,
    validate_derived_from,
    validate_used_calibration_ids,
)
from cora.data.aggregates.dataset.state import Dataset
from cora.data.features.register_dataset.command import RegisterDataset
from cora.data.features.register_dataset.context import DatasetRegistrationContext
from cora.shared.identity import ActorId


def decide(
    state: Dataset | None,
    command: RegisterDataset,
    *,
    context: DatasetRegistrationContext,
    now: datetime,
    new_id: UUID,
    registered_by: ActorId,
) -> list[DatasetRegistered]:
    """Decide the events produced by registering a new Dataset.

    Invariants:
      - State must be None (genesis-only)
        -> DatasetAlreadyExistsError
      - Name must be valid -> InvalidDatasetNameError
        (via DatasetName VO)
      - URI must be valid -> InvalidDatasetUriError (via DatasetUri VO)
      - Checksum must be valid -> InvalidDatasetChecksumError
        (via DatasetChecksum VO)
      - byte_size must be valid -> InvalidDatasetByteSizeError
        (via validate_byte_size)
      - Encoding (media_type + conforms_to) must be valid
        -> InvalidDatasetEncodingError (via DatasetEncoding VO)
      - derived_from must satisfy cardinality + UUID shape
        -> InvalidDerivedFromError (via validate_derived_from)
      - used_calibration_ids must satisfy cardinality
        -> InvalidUsedCalibrationsError (via validate_used_calibration_ids)
      - When producing_run_id is set, the Run must exist
        -> ProducingRunNotFoundError
      - When subject_id is set, the Subject must exist
        -> LinkedSubjectNotFoundError
      - All derived_from Datasets must exist
        -> DerivedFromDatasetsNotFoundError
      - No derived_from Dataset may be Discarded
        -> DerivedFromDatasetsDiscardedError
    """
    if state is not None:
        raise DatasetAlreadyExistsError(state.id)

    # Field-level validation via VOs (trims + bounded-length checks
    # + encoding-specific invariants). Each VO raises its specific
    # error class on failure, mapped to HTTP 400.
    name = DatasetName(command.name)
    uri = DatasetUri(command.uri)
    checksum = DatasetChecksum(
        algorithm=command.checksum_algorithm,
        value=command.checksum_value,
    )
    byte_size = validate_byte_size(command.byte_size)
    encoding = DatasetEncoding(
        media_type=command.media_type,
        conforms_to=command.conforms_to,
    )
    derived_from = validate_derived_from(command.derived_from)
    # cardinality-only check on the AsShot citation set.
    # NO cross-BC existence check (revision-cited atomic-ID model;
    # eventual-consistency stance per [[project_calibration_design]]
    # anti-hook #3; mirrors Run.pinned_calibration_ids decider-time
    # treatment exactly).
    used_calibration_ids = validate_used_calibration_ids(command.used_calibration_ids)

    # Cross-aggregate checks (existence-only per Q2 lock B).
    # The handler's pre-loads either populate context.* or raise
    # the not-found error before we get here; these branches are
    # the decider-level statement of the contract.
    if command.producing_run_id is not None and context.producing_run is None:
        raise ProducingRunNotFoundError(command.producing_run_id)
    if command.subject_id is not None and context.subject is None:
        raise LinkedSubjectNotFoundError(command.subject_id)
    missing_derived = sorted(
        (d for d in derived_from if d not in context.derived_from),
        key=str,
    )
    if missing_derived:
        raise DerivedFromDatasetsNotFoundError(missing_derived)
    # context.derived_from is built ONLY from command.derived_from
    # (see register_dataset/handler.py); every key here is in
    # derived_from by construction. We don't re-filter on `d in
    # derived_from`.
    discarded_derived = sorted(
        (
            d
            for d, loaded in context.derived_from.items()
            if loaded.status is DatasetStatus.DISCARDED
        ),
        key=str,
    )
    if discarded_derived:
        raise DerivedFromDatasetsDiscardedError(discarded_derived)

    # capture producing Run's terminal status at registration
    # (per non-determinism principle: capture, don't recompute). The
    # Run is in some end state by the time a Dataset references it
    # — production scenario expects Completed, but the Run may be
    # Running / Held / Aborted / Stopped / Truncated at register time
    # because in-situ measurements register Datasets while the Run
    # is still active. The captured value powers promote_dataset's
    # Run-must-be-Completed guard later.
    producing_run_end_state: str | None = (
        context.producing_run.status.value if context.producing_run is not None else None
    )

    return [
        DatasetRegistered(
            dataset_id=new_id,
            name=name.value,
            uri=uri.value,
            checksum_algorithm=checksum.algorithm,
            checksum_value=checksum.value,
            byte_size=byte_size,
            media_type=encoding.media_type,
            conforms_to=encoding.conforms_to,
            producing_run_id=command.producing_run_id,
            subject_id=command.subject_id,
            derived_from=derived_from,
            occurred_at=now,
            registered_by=registered_by,
            producing_run_end_state=producing_run_end_state,
            # raw ActuationKind value the orchestrator captured from the
            # producing conduct (None for non-conducted registrations); the
            # promote gate blocks Simulated / Hybrid.
            producing_actuation_kind=command.actuation_kind,
            # intent defaults to "Trial" on the dataclass; promotion is a
            # separate explicit slice (promote_dataset).
            # sort before emit so the event-payload bytes are
            # deterministic (matches Run.pinned_calibration_ids
            # decider-time treatment + the derived_from sorted-list
            # precedent on the same payload).
            used_calibration_ids=tuple(sorted(used_calibration_ids)),
        )
    ]
