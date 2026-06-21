"""Pure decider for the `RegisterDistribution` command.

Pure function: given the (always None) Distribution state, a
`RegisterDistribution` command, and a pre-loaded
`DistributionRegistrationContext`, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Firing order

Per [[project-data-distribution-design]] L17 (re-stated here so
the order is local-and-greppable on the decider source):

  1. Pydantic 422 boundary parse-shape (off-decider).
  2. VO field validation: DistributionUri, reused DatasetChecksum,
     reused DatasetEncoding raise `Invalid*Error`.
  3. Defensive `InvalidAccessProtocolError` re-check (in-process
     callers bypassing the boundary).
  4. State-is-None genesis guard ->
     `DistributionAlreadyExistsError`. Fires BEFORE the
     Dataset/Supply context checks because if the stream already
     has events, the conflict is unambiguous regardless of other
     fields.
  5. (handler) Dataset pre-load -> `DatasetNotFoundError` (NOT
     here; the context's `dataset` is non-None by handler
     contract).
  6. `context.dataset.status == DISCARDED` ->
     `DistributionCannotRegisterOnDiscardedDatasetError`.
  7. (handler) SupplyLookup -> `DistributionSupplyNotFoundError`
     (NOT here; the context's `supply` is non-None by handler
     contract).
  8. `context.supply.kind != "Storage"` ->
     `DistributionCannotRegisterOnNonStorageSupplyError`. Per L28
     status-agnostic bind: every Supply lifecycle is acceptable
     so long as kind is Storage.
  9. `command.checksum_algorithm != context.dataset.checksum.algorithm`
     -> `DistributionChecksumAlgorithmMismatchError` (checked before the
     value, since two 64-hex values under different algorithms are not
     comparable).
  9b. `command.checksum_value != context.dataset.checksum.value`
     -> `DistributionChecksumMismatchError`.
  10. `command.byte_size != context.dataset.byte_size` ->
      `DistributionByteSizeMismatchError`.
  11. Emit `DistributionRegistered`.
  12. Writer-side, post-request: projection UNIQUE INDEX collision
      handled by the projection writer (L31; NOT decider concern).

## VO trim semantics

Field VOs (`DistributionUri`, `DatasetChecksum`, `DatasetEncoding`)
handle their own trimming + validation in `__post_init__`; the
on-the-wire payload carries the trimmed values (so the persisted
event payload is canonical).
"""

from datetime import datetime
from uuid import UUID

from cora.data.aggregates.dataset import (
    DatasetChecksum,
    DatasetEncoding,
    DatasetStatus,
    InvalidDatasetChecksumError,
    InvalidDatasetEncodingError,
)
from cora.data.aggregates.distribution import (
    STORAGE_SUPPLY_KIND,
    AccessProtocol,
    Distribution,
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumAlgorithmMismatchError,
    DistributionChecksumMismatchError,
    DistributionRegistered,
    DistributionUri,
    InvalidAccessProtocolError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    validate_distribution_byte_size,
)
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.context import (
    DistributionRegistrationContext,
)
from cora.shared.identity import ActorId


def decide(
    state: Distribution | None,
    command: RegisterDistribution,
    *,
    context: DistributionRegistrationContext,
    now: datetime,
    new_id: UUID,
    registered_by: ActorId,
) -> list[DistributionRegistered]:
    """Decide the events produced by registering a new Distribution.

    Invariants:
      (Firing order per [[project-data-distribution-design]] L17.)
      - URI must be valid -> InvalidDistributionUriError
      - Checksum shape must be valid -> InvalidDistributionChecksumError
      - byte_size must be valid -> InvalidDistributionByteSizeError
      - Encoding shape must be valid -> InvalidDistributionEncodingError
      - access_protocol must be in closed enum
        -> InvalidAccessProtocolError
      - State must be None (genesis-only)
        -> DistributionAlreadyExistsError
      - Dataset must not be Discarded
        -> DistributionCannotRegisterOnDiscardedDatasetError
      - Supply.kind must be "Storage"
        -> DistributionCannotRegisterOnNonStorageSupplyError
      - Checksum algorithm equality vs Dataset (checked before value)
        -> DistributionChecksumAlgorithmMismatchError
      - Checksum value equality vs Dataset
        -> DistributionChecksumMismatchError
      - byte_size equality vs Dataset
        -> DistributionByteSizeMismatchError
    """
    # Step 2: VO field validation. Each VO raises its specific error
    # class on failure (mapped to HTTP 400). DatasetChecksum and
    # DatasetEncoding are reused verbatim per L8; the decider catches
    # their Dataset-prefixed exceptions and re-raises with
    # Distribution-prefixed context so the operator-facing log says
    # "register_distribution" not "register_dataset".
    uri = DistributionUri(command.uri)
    try:
        checksum = DatasetChecksum(
            algorithm=command.checksum_algorithm,
            value=command.checksum_value,
        )
    except InvalidDatasetChecksumError as exc:
        raise InvalidDistributionChecksumError(
            algorithm=command.checksum_algorithm,
            value=command.checksum_value,
            reason=str(exc),
        ) from exc
    byte_size = validate_distribution_byte_size(command.byte_size)
    try:
        encoding = DatasetEncoding(
            media_type=command.media_type,
            conforms_to=command.conforms_to,
        )
    except InvalidDatasetEncodingError as exc:
        raise InvalidDistributionEncodingError(reason=str(exc)) from exc

    # Step 3: defensive AccessProtocol re-check. The REST + MCP boundary
    # rejects out-of-enum values at 422; this branch fires when an
    # in-process caller (saga, atomic cross-BC write, test) bypasses
    # the boundary with a bare string.
    try:
        access_protocol = AccessProtocol(command.access_protocol)
    except ValueError as exc:
        raise InvalidAccessProtocolError(command.access_protocol) from exc

    # Step 4: State-is-None genesis guard. Fires before Dataset / Supply
    # context checks per L17.
    if state is not None:
        raise DistributionAlreadyExistsError(state.id)

    # Step 6: Dataset status guard (Discarded means bytes have been
    # deleted from storage; cannot bind a new copy).
    if context.dataset.status is DatasetStatus.DISCARDED:
        raise DistributionCannotRegisterOnDiscardedDatasetError(dataset_id=context.dataset.id)

    # Step 8: Supply kind guard. Status-agnostic per L28: every Supply
    # lifecycle is acceptable, only kind is gated.
    if context.supply.kind != STORAGE_SUPPLY_KIND:
        raise DistributionCannotRegisterOnNonStorageSupplyError(
            supply_id=context.supply.supply_id,
            actual_kind=context.supply.kind,
        )

    # Steps 9 + 10: byte-identical-copy invariants. The Dataset is
    # already loaded in the context (free O(1) checks). Algorithm is
    # compared first: two 64-hex values under different algorithms
    # (sha256 vs sha256-tree) are not comparable, so a value match would
    # be meaningless without it.
    if checksum.algorithm != context.dataset.checksum.algorithm:
        raise DistributionChecksumAlgorithmMismatchError(
            dataset_id=context.dataset.id,
            expected_algorithm=context.dataset.checksum.algorithm,
            actual_algorithm=checksum.algorithm,
        )
    if checksum.value != context.dataset.checksum.value:
        raise DistributionChecksumMismatchError(
            dataset_id=context.dataset.id,
            expected_checksum=context.dataset.checksum.value,
            actual_checksum=checksum.value,
        )
    if byte_size != context.dataset.byte_size:
        raise DistributionByteSizeMismatchError(
            dataset_id=context.dataset.id,
            expected_byte_size=context.dataset.byte_size,
            actual_byte_size=byte_size,
        )

    # Step 11: emit DistributionRegistered. The event payload carries
    # primitive types only per CONTRIBUTING.md "Primitives in event
    # payloads"; VOs reconstructed by the evolver on fold.
    return [
        DistributionRegistered(
            distribution_id=new_id,
            dataset_id=command.dataset_id,
            supply_id=command.supply_id,
            uri=uri.value,
            checksum_algorithm=checksum.algorithm,
            checksum_value=checksum.value,
            byte_size=byte_size,
            media_type=encoding.media_type,
            conforms_to=encoding.conforms_to,
            access_protocol=access_protocol.value,
            occurred_at=now,
            registered_by=registered_by,
        )
    ]
