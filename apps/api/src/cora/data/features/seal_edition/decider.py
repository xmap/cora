"""Pure decider for the `SealEdition` command.

## Firing order (per design memo L15)

  1. Pydantic 422 (off-decider)
  2. UnauthorizedError (handler pre-decider)
  3. EditionNotFoundError (handler load + fold)
  4. EditionCannotSealError (status guard FIRST among invariants; cheap)
  5. EditionRequiresAtLeastOneDatasetError (in-memory)
  6. Handler bulk-loads Datasets + canonical Distributions
  7. EditionCannotSealOnDiscardedDatasetError (offending dataset_ids)
  8. EditionDatasetsNotAllProductionError (offending (id, intent) pairs)
  9. EditionDatasetDistributionNotFoundError (missing canonical Distr)
  10. EditionLicenseRequiredForKindError (pure decider-on-state check)
  11. Handler FacilityLookup.lookup_by_code -> EditionPublisherNotFoundError
  12. Handler EditionSerializer.serialize -> EditionSerializerError
  13. Handler computes sha256 + publication_year + effective_license
  14. Decider emits EditionSealed
"""

from datetime import datetime

from cora.data.aggregates.dataset import Intent
from cora.data.aggregates.dataset.state import DatasetStatus
from cora.data.aggregates.edition import (
    LICENSE_REQUIRED_KINDS,
    Edition,
    EditionCannotSealError,
    EditionCannotSealOnDiscardedDatasetError,
    EditionDatasetDistributionNotFoundError,
    EditionDatasetsNotAllProductionError,
    EditionLicenseRequiredForKindError,
    EditionRequiresAtLeastOneDatasetError,
    EditionSealed,
    EditionStatus,
)
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.seal_edition.context import SealEditionContext
from cora.shared.identity import ActorId


def decide(
    state: Edition,
    command: SealEdition,
    *,
    context: SealEditionContext,
    now: datetime,
    sealed_by: ActorId,
) -> list[EditionSealed]:
    """Decide the events produced by sealing a Registered Edition.

    `state` is non-None (handler raised `EditionNotFoundError` if it
    were). Firing order per the docstring header.

    Invariants:
      (Firing order per the module docstring header.)
      - state.status must be REGISTERED -> EditionCannotSealError
      - state.dataset_ids must be non-empty
        -> EditionRequiresAtLeastOneDatasetError
      - no member Dataset may be Discarded
        -> EditionCannotSealOnDiscardedDatasetError
      - every member Dataset must have Production intent
        -> EditionDatasetsNotAllProductionError
      - every member Dataset must have a canonical Distribution row
        -> EditionDatasetDistributionNotFoundError
      - kind in {DataCite, Croissant} requires non-None license
        -> EditionLicenseRequiredForKindError
    """
    _ = command  # contained in `context` after handler resolution

    if state.status is not EditionStatus.REGISTERED:
        raise EditionCannotSealError(edition_id=state.id, current_status=state.status)

    if not state.dataset_ids:
        raise EditionRequiresAtLeastOneDatasetError(edition_id=state.id)

    discarded_ids = tuple(
        sorted(
            dataset_id
            for dataset_id, dataset in context.datasets.items()
            if dataset.status is DatasetStatus.DISCARDED
        )
    )
    if discarded_ids:
        raise EditionCannotSealOnDiscardedDatasetError(
            edition_id=state.id,
            dataset_ids=discarded_ids,
        )

    offenders = [
        (dataset_id, dataset.intent.value)
        for dataset_id, dataset in context.datasets.items()
        if dataset.intent is not Intent.PRODUCTION
    ]
    if offenders:
        raise EditionDatasetsNotAllProductionError(
            edition_id=state.id,
            offenders=tuple(sorted(offenders)),
        )

    missing_distribution_ids = tuple(
        sorted(
            dataset_id
            for dataset_id in context.datasets
            if dataset_id not in context.dataset_ids_with_canonical_distribution
        )
    )
    if missing_distribution_ids:
        raise EditionDatasetDistributionNotFoundError(
            edition_id=state.id,
            dataset_ids=missing_distribution_ids,
        )

    if state.kind in LICENSE_REQUIRED_KINDS:
        effective_license = context.license
        if effective_license is None:
            raise EditionLicenseRequiredForKindError(
                edition_id=state.id,
                kind=state.kind,
            )

    return [
        EditionSealed(
            edition_id=state.id,
            content_hash=context.content_hash,
            publisher_facility_code=context.publisher_facility_code,
            publication_year=context.publication_year,
            license=context.license,
            sealed_dataset_ids=tuple(sorted(state.dataset_ids)),
            occurred_at=now,
            sealed_by=sealed_by,
        )
    ]
